from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import g, request
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.appointments import appointments_bp
from app.extensions import db
from app.models import Appointment, AppointmentEvent, Institution, Package
from app.services.permissions import ROLE_USER, roles_required


ACTIVE_CAPACITY_STATUSES = ("unfulfilled", "awaiting_report", "fulfilled")
BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _business_today():
    return datetime.now(BUSINESS_TIMEZONE).date()


def _parse_bookable_date(raw_value):
    try:
        appointment_date = date.fromisoformat(str(raw_value))
    except (TypeError, ValueError):
        return None, ({"message": "appointment_date must be YYYY-MM-DD"}, 400)
    today = _business_today()
    if appointment_date < today or appointment_date > today + timedelta(days=30):
        return None, ({"message": "appointments are available from today through the next 30 days"}, 400)
    return appointment_date, None


def _booked_count(institution_id, appointment_date):
    return Appointment.query.filter(
        Appointment.institution_id == institution_id,
        Appointment.appointment_date == appointment_date,
        Appointment.status.in_(ACTIVE_CAPACITY_STATUSES),
    ).count()


def _availability_payload(institution, appointment_date):
    booked = _booked_count(institution.id, appointment_date)
    limit = institution.daily_appointment_limit
    remaining = None if limit is None else max(limit - booked, 0)
    return {
        "institution": institution.to_dict(),
        "appointment_date": appointment_date.isoformat(),
        "daily_limit": limit,
        "booked_count": booked,
        "remaining": remaining,
        "is_full": remaining == 0 if remaining is not None else False,
        "packages": [
            item.to_dict()
            for item in Package.query.filter_by(institution_id=institution.id, is_active=True)
            .order_by(Package.id.asc()).all()
        ],
    }


@appointments_bp.get("/availability")
@roles_required(ROLE_USER)
def availability():
    appointment_date, error = _parse_bookable_date(request.args.get("appointment_date"))
    if error:
        return error
    institutions = Institution.query.filter_by(is_active=True).order_by(Institution.id.asc()).all()
    return {"appointment_date": appointment_date.isoformat(), "items": [_availability_payload(item, appointment_date) for item in institutions]}, 200


@appointments_bp.get("")
@roles_required(ROLE_USER)
def list_appointments():
    rows = Appointment.query.filter_by(user_id=g.current_user.id).order_by(
        Appointment.appointment_date.desc(), Appointment.id.desc()
    ).all()
    return {"items": [item.to_dict() for item in rows]}, 200


@appointments_bp.post("")
@roles_required(ROLE_USER)
def create_appointment():
    payload = request.get_json(silent=True) or {}
    appointment_date, error = _parse_bookable_date(payload.get("appointment_date"))
    if error:
        return error
    try:
        institution_id = int(payload.get("institution_id"))
        package_id = int(payload.get("package_id"))
    except (TypeError, ValueError):
        return {"message": "institution_id and package_id must be integers"}, 400

    institution = Institution.query.filter_by(id=institution_id, is_active=True).first()
    package = Package.query.filter_by(id=package_id, institution_id=institution_id, is_active=True).first()
    if institution is None:
        return {"message": "institution not found"}, 404
    if package is None:
        return {"message": "active approved package not found"}, 404

    # A no-op row update serializes capacity checks in both SQLite and openGauss.
    db.session.execute(
        update(Institution).where(Institution.id == institution.id).values(
            daily_appointment_limit=Institution.daily_appointment_limit
        ).execution_options(synchronize_session=False)
    )
    db.session.refresh(institution)
    booked = _booked_count(institution.id, appointment_date)
    if institution.daily_appointment_limit is not None and booked >= institution.daily_appointment_limit:
        db.session.rollback()
        return {"message": "今日已无预约名额", "code": "APPOINTMENT_FULL"}, 409

    item = Appointment(
        user_id=g.current_user.id,
        institution_id=institution.id,
        package_id=package.id,
        appointment_date=appointment_date,
        active_date_key=appointment_date,
        status="unfulfilled",
        user_name_snapshot=g.current_user.real_name or g.current_user.username,
        user_health_id_snapshot=g.current_user.health_id,
        package_name_snapshot=package.name,
        package_price_snapshot=package.price,
    )
    db.session.add(item)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {"message": "同一用户同一天只能保留一条有效预约"}, 409
    return {"item": item.to_dict()}, 201


@appointments_bp.post("/<int:appointment_id>/cancel")
@roles_required(ROLE_USER)
def cancel_appointment(appointment_id):
    item = Appointment.query.filter_by(id=appointment_id, user_id=g.current_user.id).first()
    if item is None:
        return {"message": "appointment not found"}, 404
    if item.status != "unfulfilled":
        return {"message": "only unfulfilled appointments can be cancelled"}, 409
    item.status = "cancelled"
    item.active_date_key = None
    item.cancelled_at = datetime.now(timezone.utc)
    db.session.add(AppointmentEvent(appointment_id=item.id, event_type="cancelled", status_snapshot="cancelled",
                                    message="预约已取消", actor_user_id=g.current_user.id, occurred_at=item.cancelled_at))
    from app.booking_v7.routes import _lock_capacity, enqueue_available
    slot = _lock_capacity(item.institution, item.appointment_date); slot.revision += 1
    enqueue_available(item.institution, item.appointment_date, slot)
    db.session.commit()
    return {"item": item.to_dict()}, 200

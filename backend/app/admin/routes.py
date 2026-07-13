from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime, timezone

from flask import current_app, g, request
from sqlalchemy import func, or_, update
from sqlalchemy.exc import IntegrityError

from app.admin import admin_bp
from app.extensions import db
from app.models import (
    Comment,
    HealthIndicator,
    HealthRecord,
    IndicatorDict,
    Institution,
    InstitutionImage,
    InstitutionInvite,
    Package,
    User,
)
from app.services.institution_management import (
    ManagementValidationError,
    apply_institution_payload,
    apply_package_payload,
    delete_institution_image,
    image_payload,
    institution_payload as _base_institution_payload,
    reorder_institution_images,
    save_institution_image,
)
from app.services.indicator_values import (
    IndicatorValueError,
    evaluate_is_abnormal,
    normalize_indicator_value,
)
from app.services.permissions import ROLE_ADMIN, roles_required
from app.services.record_files import delete_report_urls


def institution_payload(institution: Institution) -> dict:
    return _base_institution_payload(institution, include_administrator=True)


def _parse_optional_int(raw_value):
    if raw_value in {None, ""}:
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _parse_date(raw_value):
    try:
        return date.fromisoformat(str(raw_value))
    except (TypeError, ValueError):
        return None


def _pagination_args():
    page = _parse_optional_int(request.args.get("page")) or 1
    page_size = _parse_optional_int(request.args.get("page_size")) or 20
    return max(page, 1), min(max(page_size, 1), 100)


def _pagination_payload(pagination):
    return {
        "page": pagination.page,
        "page_size": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    }


def _invite_hash(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode("utf-8")).hexdigest()


def _generate_invite_code() -> str:
    byte_count = max(int(current_app.config.get("INVITE_CODE_BYTES", 8)), 4)
    compact = secrets.token_hex(byte_count).upper()
    return "-".join(compact[index : index + 4] for index in range(0, len(compact), 4))


def _get_institution_or_404(institution_id: int):
    institution = db.session.get(Institution, institution_id)
    if institution is None:
        return None, ({"message": "institution not found"}, 404)
    return institution, None


def _get_nested_package_or_404(institution_id: int, package_id: int):
    package = Package.query.filter_by(id=package_id, institution_id=institution_id).first()
    if package is None:
        return None, ({"message": "package not found"}, 404)
    return package, None


def _resolve_institution_package(institution_id, package_id):
    institution = db.session.get(Institution, institution_id) if institution_id else None
    package = db.session.get(Package, package_id) if package_id else None
    if institution_id and institution is None:
        return None, None, ({"message": "institution not found"}, 404)
    if package_id and package is None:
        return None, None, ({"message": "package not found"}, 404)
    if package is not None and institution is not None and package.institution_id != institution.id:
        return None, None, ({"message": "package does not belong to the institution"}, 400)
    if package is not None and institution is None:
        institution = package.institution
    return institution, package, None


@admin_bp.get("/dashboard")
@roles_required(ROLE_ADMIN)
def dashboard():
    role_rows = db.session.query(User.role, func.count(User.id)).group_by(User.role).all()
    role_counts = {"user": 0, "institution_admin": 0, "admin": 0}
    role_counts.update({role: count for role, count in role_rows})
    invite_rows = (
        db.session.query(InstitutionInvite.status, func.count(InstitutionInvite.id))
        .group_by(InstitutionInvite.status)
        .all()
    )
    invite_counts = {"active": 0, "used": 0, "revoked": 0}
    invite_counts.update({status: count for status, count in invite_rows})
    institution_count = Institution.query.count()
    active_institution_count = Institution.query.filter_by(is_active=True).count()
    return {
        "summary": {
            "user_count": User.query.count(),
            "user_role_counts": role_counts,
            "institution_count": institution_count,
            "active_institution_count": active_institution_count,
            "inactive_institution_count": institution_count - active_institution_count,
            "invite_status_counts": invite_counts,
            "pending_comment_count": Comment.query.filter_by(is_visible=False).count(),
            "record_count": HealthRecord.query.count(),
            "confirmed_record_count": HealthRecord.query.filter_by(status="confirmed").count(),
        }
    }, 200


@admin_bp.get("/institutions")
@roles_required(ROLE_ADMIN)
def list_institutions():
    keyword = (request.args.get("keyword") or "").strip()
    active_filter = (request.args.get("is_active") or "").strip().lower()
    query = Institution.query
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                Institution.name.ilike(pattern),
                Institution.branch_name.ilike(pattern),
                Institution.district.ilike(pattern),
            )
        )
    if active_filter in {"true", "1"}:
        query = query.filter(Institution.is_active.is_(True))
    elif active_filter in {"false", "0"}:
        query = query.filter(Institution.is_active.is_(False))
    items = query.order_by(Institution.id.asc()).all()
    return {"items": [institution_payload(item) for item in items]}, 200


@admin_bp.post("/institutions")
@roles_required(ROLE_ADMIN)
def create_institution():
    payload = request.get_json(silent=True) or {}
    institution = Institution()
    try:
        apply_institution_payload(institution, payload, creating=True)
        db.session.add(institution)
        db.session.commit()
    except ManagementValidationError as exc:
        db.session.rollback()
        return {"message": str(exc)}, 400
    except IntegrityError:
        db.session.rollback()
        return {"message": "institution branch already exists"}, 409
    return {"item": institution_payload(institution)}, 201


@admin_bp.get("/institutions/<int:institution_id>")
@roles_required(ROLE_ADMIN)
def get_institution(institution_id: int):
    institution, error = _get_institution_or_404(institution_id)
    if error:
        return error
    return {"item": institution_payload(institution)}, 200


@admin_bp.put("/institutions/<int:institution_id>")
@roles_required(ROLE_ADMIN)
def update_institution(institution_id: int):
    institution, error = _get_institution_or_404(institution_id)
    if error:
        return error
    try:
        apply_institution_payload(institution, request.get_json(silent=True) or {})
        db.session.commit()
    except ManagementValidationError as exc:
        db.session.rollback()
        return {"message": str(exc)}, 400
    except IntegrityError:
        db.session.rollback()
        return {"message": "institution branch already exists"}, 409
    return {"item": institution_payload(institution)}, 200


@admin_bp.post("/institutions/<int:institution_id>/deactivate")
@roles_required(ROLE_ADMIN)
def deactivate_institution(institution_id: int):
    institution, error = _get_institution_or_404(institution_id)
    if error:
        return error
    institution.is_active = False
    if institution.administrator is not None:
        institution.administrator.role = "user"
        institution.administrator.managed_institution_id = None
    invite = institution.invite
    if invite is not None and invite.status == "active":
        invite.status = "revoked"
        invite.revoked_by_admin_id = g.current_user.id
        invite.revoked_at = datetime.now(timezone.utc)
    db.session.commit()
    return {"item": institution_payload(institution)}, 200


@admin_bp.post("/institutions/<int:institution_id>/restore")
@roles_required(ROLE_ADMIN)
def restore_institution(institution_id: int):
    institution, error = _get_institution_or_404(institution_id)
    if error:
        return error
    institution.is_active = True
    db.session.commit()
    return {"item": institution_payload(institution)}, 200


@admin_bp.get("/institutions/<int:institution_id>/packages")
@roles_required(ROLE_ADMIN)
def list_packages(institution_id: int):
    institution, error = _get_institution_or_404(institution_id)
    if error:
        return error
    items = Package.query.filter_by(institution_id=institution.id).order_by(Package.id.asc()).all()
    return {"items": [item.to_dict() for item in items]}, 200


@admin_bp.post("/institutions/<int:institution_id>/packages")
@roles_required(ROLE_ADMIN)
def create_package(institution_id: int):
    institution, error = _get_institution_or_404(institution_id)
    if error:
        return error
    package = Package(institution_id=institution.id)
    try:
        apply_package_payload(package, request.get_json(silent=True) or {}, creating=True)
        db.session.add(package)
        db.session.commit()
    except ManagementValidationError as exc:
        db.session.rollback()
        return {"message": str(exc)}, 400
    except IntegrityError:
        db.session.rollback()
        return {"message": "package name already exists for the institution"}, 409
    return {"item": package.to_dict()}, 201


@admin_bp.put("/institutions/<int:institution_id>/packages/<int:package_id>")
@roles_required(ROLE_ADMIN)
def update_package(institution_id: int, package_id: int):
    package, error = _get_nested_package_or_404(institution_id, package_id)
    if error:
        return error
    try:
        apply_package_payload(package, request.get_json(silent=True) or {})
        db.session.commit()
    except ManagementValidationError as exc:
        db.session.rollback()
        return {"message": str(exc)}, 400
    except IntegrityError:
        db.session.rollback()
        return {"message": "package name already exists for the institution"}, 409
    return {"item": package.to_dict()}, 200


@admin_bp.delete("/institutions/<int:institution_id>/packages/<int:package_id>")
@roles_required(ROLE_ADMIN)
def deactivate_package(institution_id: int, package_id: int):
    package, error = _get_nested_package_or_404(institution_id, package_id)
    if error:
        return error
    package.is_active = False
    db.session.commit()
    return {"item": package.to_dict(), "message": "package deactivated"}, 200


@admin_bp.get("/institutions/<int:institution_id>/images")
@roles_required(ROLE_ADMIN)
def list_images(institution_id: int):
    institution, error = _get_institution_or_404(institution_id)
    if error:
        return error
    return {"items": [image_payload(item) for item in institution.images], "limit": 8}, 200


@admin_bp.post("/institutions/<int:institution_id>/images")
@roles_required(ROLE_ADMIN)
def upload_image(institution_id: int):
    institution, error = _get_institution_or_404(institution_id)
    if error:
        return error
    upload = request.files.get("file")
    if upload is None:
        return {"message": "image file is required"}, 400
    try:
        image = save_institution_image(institution, upload)
    except ManagementValidationError as exc:
        return {"message": str(exc)}, 400
    return {"item": image_payload(image)}, 201


@admin_bp.put("/institutions/<int:institution_id>/images/order")
@roles_required(ROLE_ADMIN)
def reorder_images(institution_id: int):
    institution, error = _get_institution_or_404(institution_id)
    if error:
        return error
    try:
        images = reorder_institution_images(
            institution.id,
            (request.get_json(silent=True) or {}).get("image_ids"),
        )
    except ManagementValidationError as exc:
        db.session.rollback()
        return {"message": str(exc)}, 400
    return {"items": [image_payload(item) for item in images]}, 200


@admin_bp.delete("/institutions/<int:institution_id>/images/<int:image_id>")
@roles_required(ROLE_ADMIN)
def delete_image(institution_id: int, image_id: int):
    institution, error = _get_institution_or_404(institution_id)
    if error:
        return error
    if not delete_institution_image(institution.id, image_id):
        return {"message": "institution image not found"}, 404
    return {"message": "institution image deleted"}, 200


@admin_bp.get("/invites")
@roles_required(ROLE_ADMIN)
def list_invites():
    invites = InstitutionInvite.query.order_by(InstitutionInvite.issued_at.desc()).all()
    return {"items": [item.to_dict() for item in invites]}, 200


@admin_bp.get("/institutions/<int:institution_id>/invite")
@roles_required(ROLE_ADMIN)
def get_invite(institution_id: int):
    institution, error = _get_institution_or_404(institution_id)
    if error:
        return error
    return {"item": institution.invite.to_dict() if institution.invite else None}, 200


@admin_bp.post("/institutions/<int:institution_id>/invite")
@roles_required(ROLE_ADMIN)
def issue_invite(institution_id: int):
    institution, error = _get_institution_or_404(institution_id)
    if error:
        return error
    if not institution.is_active:
        return {"message": "cannot issue an invitation for an inactive institution"}, 400
    if institution.administrator is not None:
        return {"message": "institution already has an administrator"}, 409

    invite_code = _generate_invite_code()
    invite = institution.invite
    now = datetime.now(timezone.utc)
    if invite is None:
        invite = InstitutionInvite(
            institution_id=institution.id,
            code_hash=_invite_hash(invite_code),
            status="active",
            issued_by_admin_id=g.current_user.id,
            issued_at=now,
        )
        db.session.add(invite)
    else:
        replaced = db.session.execute(
            update(InstitutionInvite)
            .where(
                InstitutionInvite.id == invite.id,
                InstitutionInvite.code_hash == invite.code_hash,
                InstitutionInvite.status == invite.status,
            )
            .values(
                code_hash=_invite_hash(invite_code),
                status="active",
                issued_by_admin_id=g.current_user.id,
                used_by_user_id=None,
                revoked_by_admin_id=None,
                issued_at=now,
                used_at=None,
                revoked_at=None,
            )
            .execution_options(synchronize_session=False)
        )
        if replaced.rowcount != 1:
            db.session.rollback()
            return {"message": "invitation changed concurrently, please retry"}, 409
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {"message": "failed to issue invitation, please retry"}, 409
    invite = db.session.get(InstitutionInvite, invite.id)
    return {"item": invite.to_dict(), "invite_code": invite_code}, 201


@admin_bp.delete("/institutions/<int:institution_id>/invite")
@roles_required(ROLE_ADMIN)
def revoke_invite(institution_id: int):
    institution, error = _get_institution_or_404(institution_id)
    if error:
        return error
    invite = institution.invite
    if invite is None:
        return {"message": "invitation not found"}, 404
    if invite.status != "active":
        return {"message": "only an active invitation can be revoked"}, 409
    invite.status = "revoked"
    invite.revoked_by_admin_id = g.current_user.id
    invite.revoked_at = datetime.now(timezone.utc)
    db.session.commit()
    return {"item": invite.to_dict(), "message": "invitation revoked"}, 200


@admin_bp.post("/users/<int:user_id>/revoke-institution-admin")
@roles_required(ROLE_ADMIN)
def revoke_institution_admin(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        return {"message": "user not found"}, 404
    if user.role != "institution_admin":
        return {"message": "user is not an institution administrator"}, 400
    previous_institution_id = user.managed_institution_id
    user.role = "user"
    user.managed_institution_id = None
    db.session.commit()
    return {
        "item": user.to_dict(),
        "revoked_institution_id": previous_institution_id,
        "message": "institution administrator revoked",
    }, 200


@admin_bp.get("/records")
@roles_required(ROLE_ADMIN)
def list_records():
    page, page_size = _pagination_args()
    query = HealthRecord.query
    status = (request.args.get("status") or "").strip()
    institution_id = _parse_optional_int(request.args.get("institution_id"))
    owner_keyword = (request.args.get("owner_keyword") or "").strip()
    if status:
        if status not in {"draft", "parsed", "confirmed"}:
            return {"message": "invalid status"}, 400
        query = query.filter(HealthRecord.status == status)
    if institution_id is not None:
        query = query.filter(HealthRecord.institution_id == institution_id)
    if owner_keyword:
        query = query.join(User, HealthRecord.owner_id == User.id).filter(
            User.username.ilike(f"%{owner_keyword}%")
        )
    pagination = query.order_by(HealthRecord.exam_date.desc(), HealthRecord.id.desc()).paginate(
        page=page, per_page=page_size, error_out=False
    )
    return {
        "items": [item.to_dict(include_indicators=False) for item in pagination.items],
        "pagination": _pagination_payload(pagination),
    }, 200


@admin_bp.post("/records")
@roles_required(ROLE_ADMIN)
def create_record():
    payload = request.get_json(silent=True) or {}
    owner_id = _parse_optional_int(payload.get("owner_id"))
    owner = db.session.get(User, owner_id) if owner_id else None
    if owner is None:
        return {"message": "owner user not found"}, 404
    exam_date = _parse_date(payload.get("exam_date"))
    if exam_date is None:
        return {"message": "exam_date is required and must be ISO date (YYYY-MM-DD)"}, 400
    raw_institution_id = payload.get("institution_id")
    raw_package_id = payload.get("package_id")
    institution_id = _parse_optional_int(raw_institution_id)
    package_id = _parse_optional_int(raw_package_id)
    if raw_institution_id not in {None, ""} and institution_id is None:
        return {"message": "institution_id must be integer"}, 400
    if raw_package_id not in {None, ""} and package_id is None:
        return {"message": "package_id must be integer"}, 400
    institution, package, error = _resolve_institution_package(institution_id, package_id)
    if error:
        return error
    status = payload.get("status") or "confirmed"
    if status not in {"draft", "parsed", "confirmed"}:
        return {"message": "invalid status"}, 400
    record = HealthRecord(
        owner_id=owner.id,
        uploader_id=g.current_user.id,
        institution_id=institution.id if institution else None,
        package_id=package.id if package else None,
        exam_date=exam_date,
        status=status,
    )
    db.session.add(record)
    db.session.commit()
    return {"item": record.to_dict(include_indicators=True)}, 201


@admin_bp.get("/records/<int:record_id>")
@roles_required(ROLE_ADMIN)
def get_record(record_id: int):
    record = db.session.get(HealthRecord, record_id)
    if record is None:
        return {"message": "record not found"}, 404
    return {"item": record.to_dict(include_indicators=True)}, 200


@admin_bp.put("/records/<int:record_id>")
@roles_required(ROLE_ADMIN)
def update_record(record_id: int):
    record = db.session.get(HealthRecord, record_id)
    if record is None:
        return {"message": "record not found"}, 404
    payload = request.get_json(silent=True) or {}
    if "exam_date" in payload:
        exam_date = _parse_date(payload.get("exam_date"))
        if exam_date is None:
            return {"message": "exam_date must be ISO date (YYYY-MM-DD)"}, 400
        record.exam_date = exam_date
    if "owner_id" in payload:
        owner_id = _parse_optional_int(payload.get("owner_id"))
        if owner_id is None or db.session.get(User, owner_id) is None:
            return {"message": "owner user not found"}, 404
        record.owner_id = owner_id
    if "status" in payload:
        if payload.get("status") not in {"draft", "parsed", "confirmed"}:
            return {"message": "invalid status"}, 400
        record.status = payload["status"]

    institution_id = record.institution_id
    package_id = record.package_id
    if "institution_id" in payload:
        institution_id = _parse_optional_int(payload.get("institution_id"))
        if payload.get("institution_id") not in {None, ""} and institution_id is None:
            return {"message": "institution_id must be integer"}, 400
        if institution_id is None or institution_id != record.institution_id:
            package_id = None
    if "package_id" in payload:
        package_id = _parse_optional_int(payload.get("package_id"))
        if payload.get("package_id") not in {None, ""} and package_id is None:
            return {"message": "package_id must be integer"}, 400
    institution, package, error = _resolve_institution_package(institution_id, package_id)
    if error:
        return error
    record.institution_id = institution.id if institution else None
    record.package_id = package.id if package else None
    db.session.commit()
    return {"item": record.to_dict(include_indicators=True)}, 200


@admin_bp.post("/records/<int:record_id>/indicators")
@roles_required(ROLE_ADMIN)
def add_record_indicator(record_id: int):
    record = db.session.get(HealthRecord, record_id)
    if record is None:
        return {"message": "record not found"}, 404
    payload = request.get_json(silent=True) or {}
    indicator_dict_id = _parse_optional_int(payload.get("indicator_dict_id"))
    indicator_dict = db.session.get(IndicatorDict, indicator_dict_id) if indicator_dict_id else None
    if indicator_dict is None:
        return {"message": "indicator dict not found"}, 404
    if HealthIndicator.query.filter_by(
        record_id=record.id, indicator_dict_id=indicator_dict.id
    ).first():
        return {"message": "indicator already exists in record"}, 409
    try:
        value = normalize_indicator_value(indicator_dict, payload.get("value"))
    except IndicatorValueError as exc:
        return {"message": str(exc)}, 400
    indicator = HealthIndicator(
        record_id=record.id,
        indicator_dict_id=indicator_dict.id,
        value=value,
        is_abnormal=evaluate_is_abnormal(indicator_dict, value),
        source="manual",
    )
    db.session.add(indicator)
    db.session.commit()
    return {"item": indicator.to_dict()}, 201


@admin_bp.put("/records/<int:record_id>/indicators/<int:indicator_id>")
@roles_required(ROLE_ADMIN)
def update_record_indicator(record_id: int, indicator_id: int):
    indicator = HealthIndicator.query.filter_by(id=indicator_id, record_id=record_id).first()
    if indicator is None:
        return {"message": "indicator not found"}, 404
    payload = request.get_json(silent=True) or {}
    indicator_dict_id = _parse_optional_int(payload.get("indicator_dict_id")) or indicator.indicator_dict_id
    indicator_dict = db.session.get(IndicatorDict, indicator_dict_id)
    if indicator_dict is None:
        return {"message": "indicator dict not found"}, 404
    duplicate = HealthIndicator.query.filter(
        HealthIndicator.record_id == record_id,
        HealthIndicator.indicator_dict_id == indicator_dict.id,
        HealthIndicator.id != indicator.id,
    ).first()
    if duplicate:
        return {"message": "indicator already exists in record"}, 409
    try:
        value = normalize_indicator_value(indicator_dict, payload.get("value", indicator.value))
    except IndicatorValueError as exc:
        return {"message": str(exc)}, 400
    indicator.indicator_dict_id = indicator_dict.id
    indicator.value = value
    indicator.is_abnormal = evaluate_is_abnormal(indicator_dict, value)
    db.session.commit()
    return {"item": indicator.to_dict()}, 200


@admin_bp.delete("/records/<int:record_id>/indicators/<int:indicator_id>")
@roles_required(ROLE_ADMIN)
def delete_record_indicator(record_id: int, indicator_id: int):
    indicator = HealthIndicator.query.filter_by(id=indicator_id, record_id=record_id).first()
    if indicator is None:
        return {"message": "indicator not found"}, 404
    db.session.delete(indicator)
    db.session.commit()
    return {"message": "indicator deleted"}, 200


@admin_bp.delete("/records/<int:record_id>")
@roles_required(ROLE_ADMIN)
def delete_record(record_id: int):
    record = db.session.get(HealthRecord, record_id)
    if record is None:
        return {"message": "record not found"}, 404
    report_file_url = record.report_file_url
    db.session.delete(record)
    db.session.commit()
    delete_report_urls([report_file_url])
    return {"message": "record deleted"}, 200

from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.extensions import db
from app.models import ExamRegistration, InstitutionReport, User
from app.services.record_files import delete_report_urls


RETENTION_DAYS = 60


def utc_now():
    return datetime.now(timezone.utc)


def _comparable(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def report_is_expired(report, now=None):
    now = now or utc_now()
    return bool(report.expires_at and _comparable(report.expires_at) <= _comparable(now))


def cleanup_expired_reports(*, commit=True, now=None):
    now = now or utc_now()
    rows = InstitutionReport.query.filter(
        InstitutionReport.status == "waiting_match",
        InstitutionReport.expires_at.isnot(None),
        InstitutionReport.expires_at <= now,
    ).all()
    urls = [item.temporary_file_url for item in rows if item.temporary_file_url]
    ids = [item.id for item in rows]
    for item in rows:
        item.status = "expired"
        db.session.flush()
        db.session.delete(item)
    if commit:
        db.session.commit()
        delete_report_urls(urls)
    return ids


def _registration_for_report(report):
    user = User.query.filter_by(
        health_id=report.subject_health_id,
        real_name=report.subject_name_snapshot,
        role="user",
        is_active=True,
    ).first()
    if not user:
        return None
    return ExamRegistration.query.filter_by(
        user_id=user.id,
        institution_id=report.institution_id,
        exam_date=report.exam_date,
        status="awaiting_report",
    ).first()


def _waiting_report_for_registration(registration):
    user = db.session.get(User, registration.user_id)
    if not user or not user.real_name or not user.health_id:
        return None
    now = utc_now()
    return InstitutionReport.query.filter(
        InstitutionReport.institution_id == registration.institution_id,
        InstitutionReport.subject_health_id == user.health_id,
        InstitutionReport.subject_name_snapshot == user.real_name,
        InstitutionReport.exam_date == registration.exam_date,
        InstitutionReport.status == "waiting_match",
        InstitutionReport.expires_at > now,
    ).order_by(InstitutionReport.submitted_at.asc()).first()


def match_report_and_registration(report, registration):
    if report.status != "waiting_match" or registration.status != "awaiting_report":
        return False
    now = utc_now()
    if report_is_expired(report, now):
        return False
    report_result = db.session.execute(
        update(InstitutionReport).where(
            InstitutionReport.id == report.id,
            InstitutionReport.status == "waiting_match",
            InstitutionReport.exam_registration_id.is_(None),
            InstitutionReport.expires_at > now,
        ).values(
            status="published", matched_user_id=registration.user_id,
            exam_registration_id=registration.id, published_at=now,
        ).execution_options(synchronize_session=False)
    )
    if report_result.rowcount != 1:
        return False
    registration_result = db.session.execute(
        update(ExamRegistration).where(
            ExamRegistration.id == registration.id,
            ExamRegistration.status == "awaiting_report",
            ExamRegistration.matched_report_id.is_(None),
        ).values(status="matched", matched_report_id=report.id).execution_options(synchronize_session=False)
    )
    if registration_result.rowcount != 1:
        raise RuntimeError("registration was matched concurrently")
    db.session.flush()
    return True


def submit_report(report):
    if report.status != "locked":
        raise ValueError("only a locked report can be submitted")
    now = utc_now()
    report.status = "waiting_match"
    report.submitted_at = now
    report.expires_at = now + timedelta(days=RETENTION_DAYS)
    db.session.flush()
    registration = _registration_for_report(report)
    return bool(registration and match_report_and_registration(report, registration))


def try_match_registration(registration):
    report = _waiting_report_for_registration(registration)
    return bool(report and match_report_and_registration(report, registration))

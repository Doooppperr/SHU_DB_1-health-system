from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone

from flask import current_app, g, request
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    Appointment, IndicatorDict, Institution, InstitutionReport, Package,
    PackageChangeRequest, ReportIndicator,
)
from app.org import org_bp
from app.services import get_ocr_provider, get_storage_backend
from app.services.indicator_values import IndicatorValueError, evaluate_is_abnormal, normalize_indicator_value, normalize_ocr_indicator_value
from app.services.institution_management import (
    ManagementValidationError, apply_institution_payload, apply_package_payload,
    delete_institution_image, image_payload, institution_payload,
    reorder_institution_images, save_institution_image,
)
from app.services.ocr import mapping_service
from app.services.permissions import ROLE_INSTITUTION_ADMIN, roles_required
from app.services.package_reviews import create_change_request
from app.services.record_files import delete_report_urls
from app.services.reports import find_subject_user, submit_report


UPLOAD_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


def managed_institution():
    item = db.session.get(Institution, g.current_user.managed_institution_id)
    if item is None or not item.is_active:
        return None, ({"message": "managed institution is unavailable"}, 403)
    return item, None


def parse_date(value):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def resolve_package(institution_id, raw_id):
    if raw_id in {None, ""}:
        return None, None
    try:
        package_id = int(raw_id)
    except (TypeError, ValueError):
        return None, ({"message": "package_id must be an integer"}, 400)
    package = Package.query.filter_by(id=package_id, institution_id=institution_id, is_active=True).first()
    return (package, None) if package else (None, ({"message": "package not found"}, 404))


def scoped_report(report_id):
    institution, error = managed_institution()
    if error:
        return None, error
    report = InstitutionReport.query.filter_by(id=report_id, institution_id=institution.id).first()
    return (report, None) if report else (None, ({"message": "report not found"}, 404))


def create_report_from_payload(payload, *, temporary_file_url=None, diagnostics=None):
    institution, error = managed_institution()
    if error:
        return None, error
    try:
        appointment_id = int(payload.get("appointment_id"))
    except (TypeError, ValueError):
        return None, ({"message": "appointment_id is required"}, 400)
    appointment = Appointment.query.filter_by(id=appointment_id, institution_id=institution.id).first()
    if appointment is None:
        return None, ({"message": "appointment not found"}, 404)
    if appointment.status != "awaiting_report":
        return None, ({"message": "only appointments awaiting a report can create one"}, 409)
    if appointment.report is not None:
        return None, ({"message": "this appointment already has a report"}, 409)
    report = InstitutionReport(
        institution_id=institution.id,
        appointment_id=appointment.id,
        created_by_user_id=g.current_user.id,
        created_by_username_snapshot=g.current_user.username,
        subject_name_snapshot=appointment.user_name_snapshot,
        subject_health_id=appointment.user_health_id_snapshot,
        exam_date=appointment.appointment_date,
        package_id=appointment.package_id,
        matched_user_id=appointment.user_id,
        status="draft",
        temporary_file_url=temporary_file_url,
        ocr_diagnostics=diagnostics,
    )
    db.session.add(report)
    return report, None


@org_bp.get("/dashboard")
@roles_required(ROLE_INSTITUTION_ADMIN)
def dashboard():
    institution, error = managed_institution()
    if error:
        return error
    counts = {status: InstitutionReport.query.filter_by(institution_id=institution.id, status=status).count() for status in ("draft", "locked", "published")}
    appointment_counts = {
        status: Appointment.query.filter_by(institution_id=institution.id, status=status).count()
        for status in ("unfulfilled", "awaiting_report", "fulfilled", "invalidated", "cancelled")
    }
    return {"summary": {"institution": institution_payload(institution), "report_status_counts": counts, "appointment_status_counts": appointment_counts, "pending_package_review_count": PackageChangeRequest.query.filter_by(institution_id=institution.id, status="pending").count(), "active_package_count": Package.query.filter_by(institution_id=institution.id, is_active=True).count()}}, 200


@org_bp.get("/institution")
@roles_required(ROLE_INSTITUTION_ADMIN)
def get_institution():
    item, error = managed_institution()
    return error if error else ({"item": institution_payload(item)}, 200)


@org_bp.put("/institution")
@roles_required(ROLE_INSTITUTION_ADMIN)
def update_institution():
    item, error = managed_institution()
    if error:
        return error
    try:
        apply_institution_payload(item, request.get_json(silent=True) or {})
        db.session.commit()
    except ManagementValidationError as exc:
        db.session.rollback()
        return {"message": str(exc)}, 400
    return {"item": institution_payload(item)}, 200


@org_bp.get("/appointment-capacity")
@roles_required(ROLE_INSTITUTION_ADMIN)
def get_appointment_capacity():
    item, error = managed_institution()
    return error if error else ({"daily_appointment_limit": item.daily_appointment_limit, "unlimited": item.daily_appointment_limit is None}, 200)


@org_bp.put("/appointment-capacity")
@roles_required(ROLE_INSTITUTION_ADMIN)
def update_appointment_capacity():
    item, error = managed_institution()
    if error:
        return error
    raw = (request.get_json(silent=True) or {}).get("daily_appointment_limit")
    if raw in {None, ""}:
        item.daily_appointment_limit = None
    else:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return {"message": "daily_appointment_limit must be a positive integer or null"}, 400
        if isinstance(raw, bool) or value <= 0:
            return {"message": "daily_appointment_limit must be a positive integer or null"}, 400
        item.daily_appointment_limit = value
    db.session.commit()
    return {"daily_appointment_limit": item.daily_appointment_limit, "unlimited": item.daily_appointment_limit is None}, 200


@org_bp.get("/packages")
@roles_required(ROLE_INSTITUTION_ADMIN)
def list_packages():
    item, error = managed_institution()
    if error:
        return error
    rows = []
    for package in Package.query.filter_by(institution_id=item.id).order_by(Package.id).all():
        payload = package.to_dict()
        pending = PackageChangeRequest.query.filter_by(package_id=package.id, status="pending").first()
        payload["pending_request"] = pending.to_dict() if pending else None
        rows.append(payload)
    return {"items": rows}, 200


@org_bp.post("/packages")
@roles_required(ROLE_INSTITUTION_ADMIN)
def create_package():
    item, error = managed_institution()
    if error:
        return error
    try:
        change = create_change_request(item, g.current_user, "create", payload=request.get_json(silent=True) or {})
        db.session.commit()
    except ManagementValidationError as exc:
        db.session.rollback(); return {"message": str(exc)}, 400
    return {"item": change.to_dict(), "message": "套餐新增申请已提交审核"}, 201


@org_bp.put("/packages/<int:package_id>")
@roles_required(ROLE_INSTITUTION_ADMIN)
def update_package(package_id):
    institution, error = managed_institution()
    if error: return error
    package = Package.query.filter_by(id=package_id, institution_id=institution.id).first()
    if not package: return {"message": "package not found"}, 404
    try:
        change = create_change_request(institution, g.current_user, "update", package=package, payload=request.get_json(silent=True) or {})
        db.session.commit()
    except ManagementValidationError as exc:
        db.session.rollback(); return {"message": str(exc)}, 400
    return {"item": change.to_dict(), "message": "套餐修改申请已提交审核"}, 202


@org_bp.delete("/packages/<int:package_id>")
@roles_required(ROLE_INSTITUTION_ADMIN)
def deactivate_package(package_id):
    institution, error = managed_institution()
    if error: return error
    package = Package.query.filter_by(id=package_id, institution_id=institution.id).first()
    if not package: return {"message": "package not found"}, 404
    try:
        change = create_change_request(institution, g.current_user, "deactivate", package=package)
        db.session.commit()
    except ManagementValidationError as exc:
        db.session.rollback(); return {"message": str(exc)}, 400
    return {"item": change.to_dict(), "message": "套餐下架申请已提交审核"}, 202


@org_bp.post("/packages/<int:package_id>/reactivate")
@roles_required(ROLE_INSTITUTION_ADMIN)
def reactivate_package(package_id):
    institution, error = managed_institution()
    if error: return error
    package = Package.query.filter_by(id=package_id, institution_id=institution.id).first()
    if not package: return {"message": "package not found"}, 404
    try:
        change = create_change_request(institution, g.current_user, "reactivate", package=package)
        db.session.commit()
    except ManagementValidationError as exc:
        db.session.rollback(); return {"message": str(exc)}, 400
    return {"item": change.to_dict(), "message": "套餐恢复申请已提交审核"}, 202


@org_bp.get("/package-change-requests")
@roles_required(ROLE_INSTITUTION_ADMIN)
def list_package_change_requests():
    institution, error = managed_institution()
    if error: return error
    rows = PackageChangeRequest.query.filter_by(institution_id=institution.id).order_by(PackageChangeRequest.requested_at.desc(), PackageChangeRequest.id.desc()).all()
    return {"items": [item.to_dict() for item in rows]}, 200


@org_bp.post("/package-change-requests/<int:request_id>/withdraw")
@roles_required(ROLE_INSTITUTION_ADMIN)
def withdraw_package_change_request(request_id):
    institution, error = managed_institution()
    if error: return error
    item = PackageChangeRequest.query.filter_by(id=request_id, institution_id=institution.id).first()
    if item is None: return {"message": "review request not found"}, 404
    if item.status != "pending": return {"message": "only pending requests can be withdrawn"}, 409
    item.status = "withdrawn"; item.withdrawn_at = datetime.now(timezone.utc)
    db.session.commit()
    return {"item": item.to_dict()}, 200


@org_bp.get("/appointments")
@roles_required(ROLE_INSTITUTION_ADMIN)
def list_appointments():
    institution, error = managed_institution()
    if error: return error
    query = Appointment.query.filter_by(institution_id=institution.id)
    status = (request.args.get("status") or "").strip()
    if status: query = query.filter_by(status=status)
    rows = query.order_by(Appointment.appointment_date.desc(), Appointment.id.desc()).all()
    return {"items": [item.to_dict(include_user=True) for item in rows]}, 200


@org_bp.post("/appointments/<int:appointment_id>/attend")
@roles_required(ROLE_INSTITUTION_ADMIN)
def attend_appointment(appointment_id):
    institution, error = managed_institution()
    if error: return error
    item = Appointment.query.filter_by(id=appointment_id, institution_id=institution.id).first()
    if item is None: return {"message": "appointment not found"}, 404
    if item.status != "unfulfilled": return {"message": "only unfulfilled appointments can be confirmed"}, 409
    item.status = "awaiting_report"; item.attended_at = datetime.now(timezone.utc)
    db.session.commit()
    return {"item": item.to_dict(include_user=True)}, 200


@org_bp.post("/appointments/<int:appointment_id>/invalidate")
@roles_required(ROLE_INSTITUTION_ADMIN)
def invalidate_appointment(appointment_id):
    institution, error = managed_institution()
    if error: return error
    item = Appointment.query.filter_by(id=appointment_id, institution_id=institution.id).first()
    if item is None: return {"message": "appointment not found"}, 404
    if item.status != "unfulfilled": return {"message": "only unfulfilled appointments can be invalidated"}, 409
    item.status = "invalidated"; item.active_date_key = None; item.invalidated_at = datetime.now(timezone.utc)
    db.session.commit()
    return {"item": item.to_dict(include_user=True)}, 200


@org_bp.get("/images")
@roles_required(ROLE_INSTITUTION_ADMIN)
def list_images():
    item, error = managed_institution(); return error if error else ({"items": [image_payload(i) for i in item.images], "limit": 8}, 200)


@org_bp.post("/images")
@roles_required(ROLE_INSTITUTION_ADMIN)
def upload_image():
    item, error = managed_institution()
    if error: return error
    upload = request.files.get("file")
    if not upload: return {"message": "image file is required"}, 400
    try: image = save_institution_image(item, upload)
    except ManagementValidationError as exc: return {"message": str(exc)}, 400
    return {"item": image_payload(image)}, 201


@org_bp.put("/images/order")
@roles_required(ROLE_INSTITUTION_ADMIN)
def reorder_images():
    item, error = managed_institution()
    if error: return error
    try: images = reorder_institution_images(item.id, (request.get_json(silent=True) or {}).get("image_ids"))
    except ManagementValidationError as exc: db.session.rollback(); return {"message": str(exc)}, 400
    return {"items": [image_payload(i) for i in images]}, 200


@org_bp.delete("/images/<int:image_id>")
@roles_required(ROLE_INSTITUTION_ADMIN)
def delete_image(image_id):
    item, error = managed_institution()
    if error: return error
    return ({"message": "institution image deleted"}, 200) if delete_institution_image(item.id, image_id) else ({"message": "institution image not found"}, 404)


@org_bp.get("/reports")
@roles_required(ROLE_INSTITUTION_ADMIN)
def list_reports():
    institution, error = managed_institution()
    if error: return error
    query = InstitutionReport.query.filter_by(institution_id=institution.id)
    status = (request.args.get("status") or "").strip()
    if status: query = query.filter_by(status=status)
    return {"items": [r.to_dict() for r in query.order_by(InstitutionReport.exam_date.desc(), InstitutionReport.id.desc()).all()]}, 200


@org_bp.post("/reports")
@roles_required(ROLE_INSTITUTION_ADMIN)
def create_report():
    report, error = create_report_from_payload(request.get_json(silent=True) or {})
    if error: return error
    try: db.session.commit()
    except IntegrityError: db.session.rollback(); return {"message": "an active report already exists for this subject and date"}, 409
    return {"item": report.to_dict(include_indicators=True)}, 201


@org_bp.get("/reports/<int:report_id>")
@roles_required(ROLE_INSTITUTION_ADMIN)
def get_report(report_id):
    report, error = scoped_report(report_id)
    return error if error else ({"item": report.to_dict(include_indicators=True)}, 200)


@org_bp.put("/reports/<int:report_id>")
@roles_required(ROLE_INSTITUTION_ADMIN)
def update_report(report_id):
    report, error = scoped_report(report_id)
    if error: return error
    if report.status != "draft": return {"message": "locked reports are immutable"}, 409
    payload = request.get_json(silent=True) or {}
    if report.appointment_id and any(key in payload for key in ("subject_name", "subject_health_id", "exam_date", "package_id")):
        return {"message": "appointment identity, date and package are immutable"}, 409
    if "subject_name" in payload: report.subject_name_snapshot = (payload.get("subject_name") or "").strip()
    if "subject_health_id" in payload: report.subject_health_id = (payload.get("subject_health_id") or "").strip().upper()
    if "exam_date" in payload:
        parsed = parse_date(payload.get("exam_date"))
        if not parsed: return {"message": "exam_date must be YYYY-MM-DD"}, 400
        report.exam_date = parsed
    if "package_id" in payload:
        package, package_error = resolve_package(report.institution_id, payload.get("package_id"))
        if package_error: return package_error
        report.package_id = package.id if package else None
    try: db.session.commit()
    except IntegrityError: db.session.rollback(); return {"message": "report update conflicts with an existing active report"}, 409
    return {"item": report.to_dict(include_indicators=True)}, 200


@org_bp.post("/reports/<int:report_id>/indicators")
@roles_required(ROLE_INSTITUTION_ADMIN)
def add_indicator(report_id):
    report, error = scoped_report(report_id)
    if error: return error
    if report.status != "draft": return {"message": "locked reports are immutable"}, 409
    payload = request.get_json(silent=True) or {}
    definition = db.session.get(IndicatorDict, payload.get("indicator_dict_id"))
    if not definition: return {"message": "indicator not found"}, 404
    try: value = normalize_indicator_value(definition, payload.get("value"))
    except IndicatorValueError as exc: return {"message": str(exc)}, 400
    row = ReportIndicator(report_id=report.id, indicator_dict_id=definition.id, value=value, is_abnormal=evaluate_is_abnormal(definition, value), input_source=payload.get("input_source") if payload.get("input_source") in {"manual", "ocr"} else "manual")
    db.session.add(row)
    try: db.session.commit()
    except IntegrityError: db.session.rollback(); return {"message": "indicator already exists in report"}, 409
    return {"item": row.to_dict()}, 201


@org_bp.put("/reports/<int:report_id>/indicators/<int:indicator_id>")
@roles_required(ROLE_INSTITUTION_ADMIN)
def update_indicator(report_id, indicator_id):
    report, error = scoped_report(report_id)
    if error: return error
    if report.status != "draft": return {"message": "locked reports are immutable"}, 409
    row = ReportIndicator.query.filter_by(id=indicator_id, report_id=report.id).first()
    if not row: return {"message": "indicator not found"}, 404
    payload = request.get_json(silent=True) or {}
    definition = db.session.get(IndicatorDict, payload.get("indicator_dict_id", row.indicator_dict_id))
    if not definition: return {"message": "indicator not found"}, 404
    try: value = normalize_indicator_value(definition, payload.get("value", row.value))
    except IndicatorValueError as exc: return {"message": str(exc)}, 400
    row.indicator_dict_id = definition.id; row.value = value; row.is_abnormal = evaluate_is_abnormal(definition, value)
    try: db.session.commit()
    except IntegrityError: db.session.rollback(); return {"message": "indicator already exists in report"}, 409
    return {"item": row.to_dict()}, 200


@org_bp.delete("/reports/<int:report_id>/indicators/<int:indicator_id>")
@roles_required(ROLE_INSTITUTION_ADMIN)
def delete_indicator(report_id, indicator_id):
    report, error = scoped_report(report_id)
    if error: return error
    if report.status != "draft": return {"message": "locked reports are immutable"}, 409
    row = ReportIndicator.query.filter_by(id=indicator_id, report_id=report.id).first()
    if not row: return {"message": "indicator not found"}, 404
    db.session.delete(row); db.session.commit(); return {"message": "indicator deleted"}, 200


@org_bp.post("/reports/ocr")
@roles_required(ROLE_INSTITUTION_ADMIN)
def ocr_report():
    upload = request.files.get("file")
    if not upload or not upload.filename: return {"message": "file is required"}, 400
    if os.path.splitext(upload.filename)[1].lower() not in UPLOAD_EXTENSIONS: return {"message": "unsupported file type"}, 400
    storage = get_storage_backend(current_app.config)
    saved = storage.save(upload, subdir="reports")
    try:
        result = get_ocr_provider(current_app.config).parse_report(saved["abs_path"])
        mapping = mapping_service.map_fields(result.get("fields", []), IndicatorDict.query.all())
        diagnostics = {"engine": result.get("engine"), "parser_version": result.get("parser_version"), **mapping.get("diagnostics", {}), "unmatched": mapping.get("unmatched", [])[:30]}
        report, error = create_report_from_payload(request.form, temporary_file_url=saved["url"], diagnostics=diagnostics)
        if error: storage.delete(saved["key"]); return error
        for candidate in mapping.get("candidate_mappings", []):
            if candidate.get("requires_review"): continue
            definition = db.session.get(IndicatorDict, candidate["indicator_dict_id"])
            try: value = normalize_ocr_indicator_value(definition, candidate["value"])
            except IndicatorValueError: continue
            report.indicators.append(ReportIndicator(indicator_dict_id=definition.id, value=value, is_abnormal=evaluate_is_abnormal(definition, value), input_source="ocr"))
        db.session.commit()
    except Exception:
        db.session.rollback(); storage.delete(saved["key"]); raise
    return {"item": report.to_dict(include_indicators=True), "ocr": {"candidate_mappings": mapping.get("candidate_mappings", []), "diagnostics": diagnostics}}, 201


@org_bp.post("/reports/<int:report_id>/lock")
@roles_required(ROLE_INSTITUTION_ADMIN)
def lock_report(report_id):
    report, error = scoped_report(report_id)
    if error: return error
    if report.status != "draft": return {"message": "only draft reports can be locked"}, 409
    if not report.indicators: return {"message": "at least one indicator is required"}, 400
    if find_subject_user(report) is None:
        return {"message": "registered user not found or identity does not match"}, 409
    temp_url = report.temporary_file_url
    report.status = "locked"; report.locked_at = datetime.now(timezone.utc); report.temporary_file_url = None
    if report.ocr_diagnostics: report.ocr_diagnostics = {key: value for key, value in report.ocr_diagnostics.items() if key not in {"raw_text", "fields", "provider_response"}}
    db.session.commit(); delete_report_urls([temp_url])
    return {"item": report.to_dict(include_indicators=True)}, 200


@org_bp.post("/reports/<int:report_id>/submit")
@roles_required(ROLE_INSTITUTION_ADMIN)
def submit(report_id):
    report, error = scoped_report(report_id)
    if error: return error
    try:
        submit_report(report)
        if report.appointment is not None:
            if report.appointment.status != "awaiting_report":
                raise ValueError("appointment is not awaiting a report")
            report.appointment.status = "fulfilled"
            report.appointment.fulfilled_at = datetime.now(timezone.utc)
        db.session.commit()
    except ValueError as exc: db.session.rollback(); return {"message": str(exc)}, 409
    except IntegrityError: db.session.rollback(); return {"message": "report publishing conflict; reload and retry"}, 409
    db.session.refresh(report)
    return {"item": report.to_dict(include_indicators=True), "match_result": "matched"}, 200

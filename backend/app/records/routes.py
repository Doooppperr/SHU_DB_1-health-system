import json
import os
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import current_app, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models import (
    FriendRelation,
    HealthIndicator,
    HealthRecord,
    IndicatorDict,
    Institution,
    Package,
    User,
)
from app.records import records_bp
from app.services import get_ocr_provider, get_storage_backend
from app.services.ocr import mapping_service


ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


def _current_user_id() -> int:
    return int(get_jwt_identity())


def _current_user():
    return db.session.get(User, _current_user_id())


def _is_admin(user: User | None) -> bool:
    return user is not None and user.role == "admin"


def _parse_exam_date(raw_value: str):
    try:
        return date.fromisoformat(raw_value)
    except (TypeError, ValueError):
        return None


def _parse_optional_int(raw_value):
    if raw_value is None or raw_value == "":
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _parse_owner_id(raw_owner_id, current_user_id: int):
    if raw_owner_id is None or raw_owner_id == "":
        return current_user_id, None

    try:
        owner_id = int(raw_owner_id)
    except (TypeError, ValueError):
        return None, {"message": "owner_id must be integer"}

    return owner_id, None


def _get_manageable_owner_ids(user: User):
    if _is_admin(user):
        return [item.id for item in User.query.order_by(User.id.asc()).all()]

    relation_rows = FriendRelation.query.filter_by(user_id=user.id, auth_status=True).all()
    owner_ids = [user.id]
    owner_ids.extend(item.friend_user_id for item in relation_rows)
    return list(dict.fromkeys(owner_ids))


def _validate_owner_manage_permission(manager_user: User, owner_id: int):
    owner_user = db.session.get(User, owner_id)
    if owner_user is None:
        return {"message": "owner user not found"}, 404

    if _is_admin(manager_user) or manager_user.id == owner_id:
        return None, None

    relation = FriendRelation.query.filter_by(user_id=manager_user.id, friend_user_id=owner_id).first()
    if relation is None:
        return {"message": "friend relation not found"}, 403

    if not relation.auth_status:
        return {"message": "friend authorization required"}, 403

    return None, None


def _can_manage_owner(user: User, owner_id: int) -> bool:
    if _is_admin(user) or user.id == owner_id:
        return True

    relation = FriendRelation.query.filter_by(
        user_id=user.id,
        friend_user_id=owner_id,
        auth_status=True,
    ).first()
    return relation is not None


def _get_accessible_record(record_id: int, user: User):
    record = db.session.get(HealthRecord, record_id)
    if record is None:
        return None

    if not _can_manage_owner(user, record.owner_id):
        return None

    return record


def _evaluate_is_abnormal(indicator_dict: IndicatorDict, value: str) -> bool:
    if indicator_dict.value_type != "numeric":
        return False

    try:
        numeric_value = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return False

    if indicator_dict.reference_low is not None and numeric_value < indicator_dict.reference_low:
        return True

    if indicator_dict.reference_high is not None and numeric_value > indicator_dict.reference_high:
        return True

    return False


def _validate_institution_package(institution_id, package_id):
    institution = db.session.get(Institution, institution_id) if institution_id else None
    if institution_id and institution is None:
        return None, None, {"message": "institution not found"}, 404

    package = db.session.get(Package, package_id) if package_id else None
    if package_id and package is None:
        return None, None, {"message": "package not found"}, 404

    if package and institution and package.institution_id != institution.id:
        return None, None, {"message": "package does not belong to the institution"}, 400

    if package and institution is None:
        institution = db.session.get(Institution, package.institution_id)

    return institution, package, None, None


@records_bp.get("")
@jwt_required()
def list_records():
    user = _current_user()
    if user is None:
        return {"message": "user not found"}, 404

    owner_ids = _get_manageable_owner_ids(user)
    records = (
        HealthRecord.query.filter(HealthRecord.owner_id.in_(owner_ids))
        .order_by(HealthRecord.exam_date.desc(), HealthRecord.id.desc())
        .all()
    )

    manageable_set = set(owner_ids)
    items = []
    for record in records:
        payload = record.to_dict(include_indicators=False)
        payload["is_owner"] = record.owner_id == user.id
        payload["can_manage"] = record.owner_id in manageable_set
        items.append(payload)

    return {"items": items}, 200


@records_bp.post("")
@jwt_required()
def create_record():
    user = _current_user()
    if user is None:
        return {"message": "user not found"}, 404

    payload = request.get_json(silent=True) or {}

    exam_date = _parse_exam_date(payload.get("exam_date"))
    if exam_date is None:
        return {"message": "exam_date is required and must be ISO date (YYYY-MM-DD)"}, 400

    owner_id, owner_parse_error = _parse_owner_id(payload.get("owner_id"), user.id)
    if owner_parse_error:
        return owner_parse_error, 400

    owner_error_payload, owner_error_status = _validate_owner_manage_permission(user, owner_id)
    if owner_error_payload:
        return owner_error_payload, owner_error_status

    institution_id = _parse_optional_int(payload.get("institution_id"))
    package_id = _parse_optional_int(payload.get("package_id"))

    institution, package, error_payload, error_status = _validate_institution_package(institution_id, package_id)
    if error_payload:
        return error_payload, error_status

    status = payload.get("status") or "confirmed"
    if status not in {"draft", "parsed", "confirmed"}:
        return {"message": "invalid status"}, 400

    record = HealthRecord(
        owner_id=owner_id,
        uploader_id=user.id,
        institution_id=institution.id if institution else None,
        package_id=package.id if package else None,
        exam_date=exam_date,
        report_file_url=payload.get("report_file_url"),
        status=status,
    )
    db.session.add(record)
    db.session.commit()

    return {"item": record.to_dict(include_indicators=True)}, 201


@records_bp.post("/upload")
@jwt_required()
def upload_record_and_parse():
    user = _current_user()
    if user is None:
        return {"message": "user not found"}, 404

    uploaded_file = request.files.get("file")

    if uploaded_file is None or not uploaded_file.filename:
        return {"message": "file is required"}, 400

    extension = os.path.splitext(uploaded_file.filename)[1].lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        return {"message": "unsupported file type"}, 400

    exam_date = _parse_exam_date(request.form.get("exam_date"))
    if exam_date is None:
        return {"message": "exam_date is required and must be ISO date (YYYY-MM-DD)"}, 400

    owner_id, owner_parse_error = _parse_owner_id(request.form.get("owner_id"), user.id)
    if owner_parse_error:
        return owner_parse_error, 400

    owner_error_payload, owner_error_status = _validate_owner_manage_permission(user, owner_id)
    if owner_error_payload:
        return owner_error_payload, owner_error_status

    institution_id = _parse_optional_int(request.form.get("institution_id"))
    package_id = _parse_optional_int(request.form.get("package_id"))

    institution, package, error_payload, error_status = _validate_institution_package(institution_id, package_id)
    if error_payload:
        return error_payload, error_status

    storage = get_storage_backend(current_app.config)
    saved_file = storage.save(uploaded_file, subdir="reports")

    provider = get_ocr_provider(current_app.config)

    try:
        ocr_result = provider.parse_report(saved_file["abs_path"])
    except Exception as exc:
        storage.delete(saved_file["key"])
        return {"message": f"ocr parse failed: {exc}"}, 500

    indicator_dicts = IndicatorDict.query.all()
    mapping = mapping_service.map_fields(ocr_result.get("fields", []), indicator_dicts)

    record = HealthRecord(
        owner_id=owner_id,
        uploader_id=user.id,
        institution_id=institution.id if institution else None,
        package_id=package.id if package else None,
        exam_date=exam_date,
        report_file_url=saved_file["url"],
        ocr_raw_text=json.dumps(ocr_result, ensure_ascii=False),
        status="parsed",
    )
    db.session.add(record)
    db.session.flush()

    for item in mapping["mapped"]:
        indicator_dict = item["indicator_dict"]
        value = item["value"]

        indicator = HealthIndicator(
            record_id=record.id,
            indicator_dict_id=indicator_dict.id,
            value=value,
            is_abnormal=_evaluate_is_abnormal(indicator_dict, value),
            source="ocr",
        )
        db.session.add(indicator)

    db.session.commit()

    return {
        "item": record.to_dict(include_indicators=True),
        "ocr": {
            "provider": ocr_result.get("engine", "unknown"),
            "mapped_count": len(mapping["mapped"]),
            "unmatched_count": len(mapping["unmatched"]),
            "unmatched_fields": mapping["unmatched"],
        },
    }, 201


@records_bp.put("/<int:record_id>/confirm")
@jwt_required()
def confirm_record(record_id: int):
    user = _current_user()
    if user is None:
        return {"message": "user not found"}, 404

    record = _get_accessible_record(record_id, user)
    if record is None:
        return {"message": "record not found"}, 404

    if record.status == "confirmed":
        return {"item": record.to_dict(include_indicators=True), "message": "already confirmed"}, 200

    if record.status not in {"draft", "parsed"}:
        return {"message": "record status cannot be confirmed"}, 400

    record.status = "confirmed"
    db.session.commit()

    return {"item": record.to_dict(include_indicators=True), "message": "record confirmed"}, 200


@records_bp.get("/<int:record_id>")
@jwt_required()
def get_record_detail(record_id: int):
    user = _current_user()
    if user is None:
        return {"message": "user not found"}, 404

    record = _get_accessible_record(record_id, user)
    if record is None:
        return {"message": "record not found"}, 404

    return {"item": record.to_dict(include_indicators=True)}, 200


@records_bp.put("/<int:record_id>")
@jwt_required()
def update_record(record_id: int):
    user = _current_user()
    if user is None:
        return {"message": "user not found"}, 404

    record = _get_accessible_record(record_id, user)
    if record is None:
        return {"message": "record not found"}, 404

    payload = request.get_json(silent=True) or {}

    if "exam_date" in payload:
        exam_date = _parse_exam_date(payload.get("exam_date"))
        if exam_date is None:
            return {"message": "exam_date must be ISO date (YYYY-MM-DD)"}, 400
        record.exam_date = exam_date

    if "owner_id" in payload:
        owner_id = _parse_optional_int(payload.get("owner_id"))
        if owner_id is None:
            return {"message": "owner_id must be integer"}, 400
        owner_error_payload, owner_error_status = _validate_owner_manage_permission(user, owner_id)
        if owner_error_payload:
            return owner_error_payload, owner_error_status
        record.owner_id = owner_id

    institution_id = record.institution_id
    package_id = record.package_id

    if "institution_id" in payload:
        raw_institution_id = payload.get("institution_id")
        if raw_institution_id in {None, ""}:
            institution_id = None
        else:
            institution_id = _parse_optional_int(raw_institution_id)
            if institution_id is None:
                return {"message": "institution_id must be integer"}, 400

    if "package_id" in payload:
        raw_package_id = payload.get("package_id")
        if raw_package_id in {None, ""}:
            package_id = None
        else:
            package_id = _parse_optional_int(raw_package_id)
            if package_id is None:
                return {"message": "package_id must be integer"}, 400

    institution, package, error_payload, error_status = _validate_institution_package(institution_id, package_id)
    if error_payload:
        return error_payload, error_status

    record.institution_id = institution.id if institution else None
    record.package_id = package.id if package else None

    if "status" in payload:
        status = payload.get("status")
        if status not in {"draft", "parsed", "confirmed"}:
            return {"message": "invalid status"}, 400
        record.status = status

    db.session.commit()
    return {"item": record.to_dict(include_indicators=True)}, 200


@records_bp.delete("/<int:record_id>")
@jwt_required()
def delete_record(record_id: int):
    user = _current_user()
    if user is None:
        return {"message": "user not found"}, 404

    record = _get_accessible_record(record_id, user)
    if record is None:
        return {"message": "record not found"}, 404

    db.session.delete(record)
    db.session.commit()
    return {"message": "record deleted"}, 200


@records_bp.post("/<int:record_id>/indicators")
@jwt_required()
def add_record_indicator(record_id: int):
    user = _current_user()
    if user is None:
        return {"message": "user not found"}, 404

    record = _get_accessible_record(record_id, user)
    if record is None:
        return {"message": "record not found"}, 404

    payload = request.get_json(silent=True) or {}
    indicator_dict_id = _parse_optional_int(payload.get("indicator_dict_id"))
    value = payload.get("value")

    if indicator_dict_id is None or value is None or str(value).strip() == "":
        return {"message": "indicator_dict_id and value are required"}, 400

    indicator_dict = db.session.get(IndicatorDict, indicator_dict_id)
    if indicator_dict is None:
        return {"message": "indicator dict not found"}, 404

    existing = HealthIndicator.query.filter_by(record_id=record.id, indicator_dict_id=indicator_dict_id).first()
    if existing is not None:
        return {"message": "indicator already exists in record"}, 409

    indicator = HealthIndicator(
        record_id=record.id,
        indicator_dict_id=indicator_dict_id,
        value=str(value).strip(),
        is_abnormal=_evaluate_is_abnormal(indicator_dict, value),
        source="manual",
    )
    db.session.add(indicator)
    db.session.commit()

    return {"item": indicator.to_dict()}, 201


@records_bp.put("/<int:record_id>/indicators/<int:indicator_id>")
@jwt_required()
def update_record_indicator(record_id: int, indicator_id: int):
    user = _current_user()
    if user is None:
        return {"message": "user not found"}, 404

    record = _get_accessible_record(record_id, user)
    if record is None:
        return {"message": "record not found"}, 404

    indicator = HealthIndicator.query.filter_by(id=indicator_id, record_id=record.id).first()
    if indicator is None:
        return {"message": "indicator not found"}, 404

    payload = request.get_json(silent=True) or {}
    value = payload.get("value", indicator.value)
    indicator_dict_id = _parse_optional_int(payload.get("indicator_dict_id")) or indicator.indicator_dict_id

    if value is None or str(value).strip() == "":
        return {"message": "value is required"}, 400

    indicator_dict = db.session.get(IndicatorDict, indicator_dict_id)
    if indicator_dict is None:
        return {"message": "indicator dict not found"}, 404

    duplicate = (
        HealthIndicator.query.filter(
            HealthIndicator.record_id == record.id,
            HealthIndicator.indicator_dict_id == indicator_dict_id,
            HealthIndicator.id != indicator.id,
        ).first()
    )
    if duplicate is not None:
        return {"message": "indicator already exists in record"}, 409

    indicator.indicator_dict_id = indicator_dict_id
    indicator.value = str(value).strip()
    indicator.is_abnormal = _evaluate_is_abnormal(indicator_dict, value)

    db.session.commit()
    return {"item": indicator.to_dict()}, 200


@records_bp.delete("/<int:record_id>/indicators/<int:indicator_id>")
@jwt_required()
def delete_record_indicator(record_id: int, indicator_id: int):
    user = _current_user()
    if user is None:
        return {"message": "user not found"}, 404

    record = _get_accessible_record(record_id, user)
    if record is None:
        return {"message": "record not found"}, 404

    indicator = HealthIndicator.query.filter_by(id=indicator_id, record_id=record.id).first()
    if indicator is None:
        return {"message": "indicator not found"}, 404

    db.session.delete(indicator)
    db.session.commit()
    return {"message": "indicator deleted"}, 200

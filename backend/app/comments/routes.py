from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.comments import comments_bp
from app.extensions import db
from app.models import Comment, HealthRecord, Institution, User


def _current_user():
    user_id = int(get_jwt_identity())
    return db.session.get(User, user_id)


def _parse_optional_int(raw_value):
    if raw_value is None or raw_value == "":
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _parse_bool(raw_value):
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, str):
        normalized = raw_value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return None


def _normalize_content(raw_value):
    return (raw_value or "").strip()


def _require_admin(user: User):
    if user is None:
        return {"message": "user not found"}, 404
    if user.role != "admin":
        return {"message": "admin permission required"}, 403
    return None, None


def _is_admin(user: User | None) -> bool:
    return user is not None and user.role == "admin"


@comments_bp.get("")
@jwt_required()
def list_comments():
    user = _current_user()
    if user is None:
        return {"message": "user not found"}, 404

    institution_id = _parse_optional_int(request.args.get("institution_id"))
    include_hidden = _parse_bool(request.args.get("include_hidden")) or False

    query = Comment.query.order_by(Comment.created_at.desc(), Comment.id.desc())
    if institution_id is not None:
        query = query.filter_by(institution_id=institution_id)

    if user.role != "admin" or not include_hidden:
        query = query.filter_by(is_visible=True)

    items = query.all()
    return {"items": [item.to_dict() for item in items]}, 200


@comments_bp.get("/mine")
@jwt_required()
def list_my_comments():
    user = _current_user()
    if user is None:
        return {"message": "user not found"}, 404

    institution_id = _parse_optional_int(request.args.get("institution_id"))
    query = Comment.query.filter_by(user_id=user.id).order_by(Comment.created_at.desc(), Comment.id.desc())
    if institution_id is not None:
        query = query.filter_by(institution_id=institution_id)

    items = query.all()
    return {"items": [item.to_dict() for item in items]}, 200


@comments_bp.post("")
@jwt_required()
def create_comment():
    user = _current_user()
    if user is None:
        return {"message": "user not found"}, 404

    payload = request.get_json(silent=True) or {}
    institution_id = _parse_optional_int(payload.get("institution_id"))
    content = (payload.get("content") or "").strip()
    rating = _parse_optional_int(payload.get("rating"))

    if institution_id is None:
        return {"message": "institution_id is required"}, 400

    institution = db.session.get(Institution, institution_id)
    if institution is None:
        return {"message": "institution not found"}, 404

    if not content:
        return {"message": "content is required"}, 400

    if len(content) > 1000:
        return {"message": "content is too long"}, 400

    if rating is None or rating < 1 or rating > 5:
        return {"message": "rating must be between 1 and 5"}, 400

    uploaded_record = HealthRecord.query.filter_by(
        uploader_id=user.id,
        institution_id=institution_id,
    ).first()
    if uploaded_record is None:
        return {
            "code": "comment_requires_record",
            "message": "upload a record for this institution before commenting",
        }, 403

    comment = Comment(
        user_id=user.id,
        institution_id=institution_id,
        content=content,
        rating=rating,
        is_visible=False,
    )
    db.session.add(comment)
    db.session.commit()

    return {"item": comment.to_dict(), "message": "comment submitted for moderation"}, 201


@comments_bp.get("/moderation")
@jwt_required()
def list_comments_for_moderation():
    user = _current_user()
    error_payload, error_status = _require_admin(user)
    if error_payload:
        return error_payload, error_status

    institution_id = _parse_optional_int(request.args.get("institution_id"))
    query = Comment.query.order_by(Comment.created_at.desc(), Comment.id.desc())
    if institution_id is not None:
        query = query.filter_by(institution_id=institution_id)

    items = query.all()
    return {"items": [item.to_dict() for item in items]}, 200


@comments_bp.put("/<int:comment_id>/visibility")
@jwt_required()
def update_comment_visibility(comment_id: int):
    user = _current_user()
    error_payload, error_status = _require_admin(user)
    if error_payload:
        return error_payload, error_status

    comment = db.session.get(Comment, comment_id)
    if comment is None:
        return {"message": "comment not found"}, 404

    payload = request.get_json(silent=True) or {}
    is_visible = _parse_bool(payload.get("is_visible"))
    if is_visible is None:
        return {"message": "is_visible must be boolean"}, 400

    comment.is_visible = is_visible
    db.session.commit()
    return {"item": comment.to_dict()}, 200


@comments_bp.put("/<int:comment_id>")
@jwt_required()
def update_comment(comment_id: int):
    user = _current_user()
    error_payload, error_status = _require_admin(user)
    if error_payload:
        return error_payload, error_status

    comment = db.session.get(Comment, comment_id)
    if comment is None:
        return {"message": "comment not found"}, 404

    payload = request.get_json(silent=True) or {}

    if "content" in payload:
        content = _normalize_content(payload.get("content"))
        if not content:
            return {"message": "content is required"}, 400
        if len(content) > 1000:
            return {"message": "content is too long"}, 400
        comment.content = content

    if "rating" in payload:
        rating = _parse_optional_int(payload.get("rating"))
        if rating is None or rating < 1 or rating > 5:
            return {"message": "rating must be between 1 and 5"}, 400
        comment.rating = rating

    if "is_visible" in payload:
        is_visible = _parse_bool(payload.get("is_visible"))
        if is_visible is None:
            return {"message": "is_visible must be boolean"}, 400
        comment.is_visible = is_visible

    db.session.commit()
    return {"item": comment.to_dict()}, 200


@comments_bp.delete("/<int:comment_id>")
@jwt_required()
def delete_comment(comment_id: int):
    user = _current_user()
    if user is None:
        return {"message": "user not found"}, 404

    comment = db.session.get(Comment, comment_id)
    if comment is None:
        return {"message": "comment not found"}, 404

    if not _is_admin(user) and comment.user_id != user.id:
        return {"message": "permission denied"}, 403

    db.session.delete(comment)
    db.session.commit()
    return {"message": "comment deleted"}, 200

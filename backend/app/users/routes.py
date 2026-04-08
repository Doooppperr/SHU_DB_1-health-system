from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import or_

from app.extensions import db
from app.models import Comment, FriendRelation, HealthRecord, User
from app.users import users_bp


ALLOWED_USER_ROLES = {"user", "admin"}


def _current_user():
    user_id = int(get_jwt_identity())
    return db.session.get(User, user_id)


def _require_admin(user: User | None):
    if user is None:
        return {"message": "user not found"}, 404
    if user.role != "admin":
        return {"message": "admin permission required"}, 403
    return None, None


@users_bp.get("/me")
@jwt_required()
def get_me():
    user = _current_user()
    if user is None:
        return {"message": "user not found"}, 404

    return {"user": user.to_dict()}, 200


@users_bp.get("")
@jwt_required()
def list_users():
    current_user = _current_user()
    error_payload, error_status = _require_admin(current_user)
    if error_payload:
        return error_payload, error_status

    users = User.query.order_by(User.id.asc()).all()
    return {"items": [item.to_dict() for item in users]}, 200


@users_bp.put("/<int:target_user_id>")
@jwt_required()
def update_user(target_user_id: int):
    current_user = _current_user()
    error_payload, error_status = _require_admin(current_user)
    if error_payload:
        return error_payload, error_status

    target_user = db.session.get(User, target_user_id)
    if target_user is None:
        return {"message": "user not found"}, 404

    payload = request.get_json(silent=True) or {}
    editable_fields = {"username", "email", "phone", "role", "password"}
    if not any(field in payload for field in editable_fields):
        return {"message": "at least one editable field is required"}, 400

    if "username" in payload:
        username = (payload.get("username") or "").strip()
        if not username:
            return {"message": "username is required"}, 400
        duplicate = User.query.filter(User.username == username, User.id != target_user.id).first()
        if duplicate is not None:
            return {"message": "username already exists"}, 409
        target_user.username = username

    if "email" in payload:
        email = (payload.get("email") or "").strip() or None
        if email:
            duplicate = User.query.filter(User.email == email, User.id != target_user.id).first()
            if duplicate is not None:
                return {"message": "email already exists"}, 409
        target_user.email = email

    if "phone" in payload:
        target_user.phone = (payload.get("phone") or "").strip() or None

    if "role" in payload:
        role = (payload.get("role") or "").strip()
        if role not in ALLOWED_USER_ROLES:
            return {"message": "invalid role"}, 400
        target_user.role = role

    if "password" in payload:
        password = payload.get("password") or ""
        if len(password) < 6:
            return {"message": "password must be at least 6 characters"}, 400
        target_user.set_password(password)

    db.session.commit()
    return {"item": target_user.to_dict()}, 200


@users_bp.delete("/<int:target_user_id>")
@jwt_required()
def delete_user(target_user_id: int):
    current_user = _current_user()
    error_payload, error_status = _require_admin(current_user)
    if error_payload:
        return error_payload, error_status

    if current_user.id == target_user_id:
        return {"message": "admin cannot delete self"}, 400

    target_user = db.session.get(User, target_user_id)
    if target_user is None:
        return {"message": "user not found"}, 404

    relations = FriendRelation.query.filter(
        or_(FriendRelation.user_id == target_user_id, FriendRelation.friend_user_id == target_user_id)
    ).all()
    for relation in relations:
        db.session.delete(relation)

    comments = Comment.query.filter_by(user_id=target_user_id).all()
    for comment in comments:
        db.session.delete(comment)

    records = HealthRecord.query.filter(
        or_(HealthRecord.owner_id == target_user_id, HealthRecord.uploader_id == target_user_id)
    ).all()
    for record in records:
        db.session.delete(record)

    db.session.delete(target_user)
    db.session.commit()

    return {"message": "user deleted"}, 200

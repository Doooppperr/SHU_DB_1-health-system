from __future__ import annotations

from functools import wraps

from flask import g
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models import User


ROLE_USER = "user"
ROLE_INSTITUTION_ADMIN = "institution_admin"
ROLE_ADMIN = "admin"
ALL_ROLES = {ROLE_USER, ROLE_INSTITUTION_ADMIN, ROLE_ADMIN}


def get_current_user() -> User | None:
    identity = get_jwt_identity()
    if identity is None:
        return None
    try:
        user_id = int(identity)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, user_id)


def role_error(user: User | None, *allowed_roles: str):
    if user is None:
        return {"message": "user not found"}, 404
    if user.role not in allowed_roles:
        return {
            "message": "permission denied",
            "required_roles": list(allowed_roles),
        }, 403
    if not user.is_active:
        return {"message": "account is inactive"}, 403
    if user.role == ROLE_INSTITUTION_ADMIN and (
        user.managed_institution is None or not user.managed_institution.is_active
    ):
        return {"message": "managed institution is inactive"}, 403
    return None


def roles_required(*allowed_roles: str):
    """Authorize using the current database role, not stale JWT role claims."""

    def decorator(view):
        @wraps(view)
        @jwt_required()
        def wrapped(*args, **kwargs):
            user = get_current_user()
            error = role_error(user, *allowed_roles)
            if error:
                return error
            g.current_user = user
            return view(*args, **kwargs)

        return wrapped

    return decorator

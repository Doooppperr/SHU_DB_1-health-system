from flask import request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)

from app.auth import auth_bp
from app.extensions import db
from app.models import User


@auth_bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    email = (payload.get("email") or "").strip() or None
    phone = (payload.get("phone") or "").strip() or None

    if not username or not password:
        return {"message": "username and password are required"}, 400

    if len(password) < 6:
        return {"message": "password must be at least 6 characters"}, 400

    if User.query.filter_by(username=username).first():
        return {"message": "username already exists"}, 409

    if email and User.query.filter_by(email=email).first():
        return {"message": "email already exists"}, 409

    user = User(username=username, email=email, phone=phone)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return {"message": "register success", "user": user.to_dict()}, 201


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    if not username or not password:
        return {"message": "username and password are required"}, 400

    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        return {"message": "invalid username or password"}, 401

    claims = {"role": user.role}
    access_token = create_access_token(identity=str(user.id), additional_claims=claims)
    refresh_token = create_refresh_token(identity=str(user.id), additional_claims=claims)

    return {
        "message": "login success",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_dict(),
    }, 200


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh_token():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))
    if user is None:
        return {"message": "user not found"}, 404

    access_token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return {"access_token": access_token}, 200


@auth_bp.post("/logout")
@jwt_required()
def logout():
    return {"message": "logout success"}, 200

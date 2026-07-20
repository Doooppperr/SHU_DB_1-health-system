import base64
import hashlib
import secrets
import time
from datetime import datetime, timezone
from uuid import uuid4

from flask import current_app, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.auth import auth_bp
from app.extensions import db
from app.models import InstitutionInvite, User
from app.services.contact import is_valid_email, normalize_email


CAPTCHA_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
HEALTH_ID_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
_captcha_store = {}


def _purge_expired_captchas(now=None):
    now = now or time.time()
    expired_ids = [
        challenge_id
        for challenge_id, challenge in _captcha_store.items()
        if challenge["expires_at"] <= now
    ]
    for challenge_id in expired_ids:
        _captcha_store.pop(challenge_id, None)


def _generate_captcha_code(length=4):
    return "".join(secrets.choice(CAPTCHA_ALPHABET) for _ in range(length))


def _random_between(min_value, max_value):
    return min_value + secrets.randbelow(max_value - min_value + 1)


def _build_captcha_image(code):
    width = 128
    height = 44
    line_colors = ["#9db4c7", "#b6c4d2", "#a5b8a0", "#d0b47f", "#c2a2a2"]
    text_colors = ["#1f4b5f", "#34543f", "#6a4a1c", "#573c6b"]

    lines = []
    for _ in range(7):
        color = secrets.choice(line_colors)
        lines.append(
            f'<line x1="{_random_between(0, width)}" y1="{_random_between(0, height)}" '
            f'x2="{_random_between(0, width)}" y2="{_random_between(0, height)}" '
            f'stroke="{color}" stroke-width="{_random_between(1, 2)}" opacity="0.75" />'
        )

    chars = []
    for index, char in enumerate(code):
        x = 20 + index * 26 + _random_between(-3, 3)
        y = 29 + _random_between(-3, 4)
        angle = _random_between(-15, 15)
        color = secrets.choice(text_colors)
        chars.append(
            f'<text x="{x}" y="{y}" transform="rotate({angle} {x} {y})" '
            f'fill="{color}" font-size="24" font-family="Consolas, Arial, sans-serif" '
            f'font-weight="700">{char}</text>'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" rx="6" fill="#f3f7fb" />'
        + "".join(lines)
        + "".join(chars)
        + "</svg>"
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _create_captcha_challenge():
    now = time.time()
    _purge_expired_captchas(now)

    code = _generate_captcha_code()
    challenge_id = uuid4().hex
    ttl_seconds = current_app.config.get("CAPTCHA_TTL_SECONDS", 300)
    _captcha_store[challenge_id] = {
        "answer": code,
        "expires_at": now + ttl_seconds,
    }

    return challenge_id, code, _build_captcha_image(code)


def _verify_captcha(challenge_id, answer):
    _purge_expired_captchas()
    challenge = _captcha_store.pop(challenge_id, None)
    if not challenge:
        return False
    return secrets.compare_digest(challenge["answer"], answer.strip().upper())


def _build_auth_payload(user, message):
    claims = {"role": user.role}
    access_token = create_access_token(identity=str(user.id), additional_claims=claims)
    refresh_token = create_refresh_token(identity=str(user.id), additional_claims=claims)
    return {
        "message": message,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_dict(),
    }


def _invite_code_hash(invite_code: str) -> str:
    normalized = invite_code.strip().upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _new_health_id() -> str:
    for _ in range(20):
        candidate = "HID-" + "".join(secrets.choice(HEALTH_ID_ALPHABET) for _ in range(8))
        if User.query.filter_by(health_id=candidate).first() is None:
            return candidate
    raise RuntimeError("unable to allocate a unique health identity")


@auth_bp.get("/captcha")
def captcha():
    challenge_id, code, image = _create_captcha_challenge()
    payload = {
        "captcha_id": challenge_id,
        "image": image,
    }
    if current_app.config.get("TESTING"):
        payload["captcha_answer"] = code
    return payload, 200


@auth_bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    email = normalize_email(payload.get("email"))
    phone = (payload.get("phone") or "").strip() or None
    invite_code = (payload.get("invite_code") or "").strip()
    captcha_id = (payload.get("captcha_id") or "").strip()
    captcha_answer = (payload.get("captcha_answer") or "").strip()

    if not username or not password or not email or not captcha_id or not captcha_answer:
        return {"message": "用户名、邮箱、密码和图片验证码均为必填项"}, 400
    if not is_valid_email(email):
        return {"message": "请输入有效的邮箱地址"}, 400

    if len(password) < 6:
        return {"message": "password must be at least 6 characters"}, 400

    if not _verify_captcha(captcha_id, captcha_answer):
        return {"message": "invalid captcha"}, 400

    if User.query.filter_by(username=username).first():
        return {"message": "username already exists"}, 409

    invite = None
    expected_invite_hash = None
    if invite_code:
        invite = InstitutionInvite.query.filter_by(
            code_hash=_invite_code_hash(invite_code),
            status="active",
        ).first()
        if invite is None or invite.used_by_user_id is not None:
            return {"message": "invalid or unavailable invitation code"}, 400
        if invite.institution is None or not invite.institution.is_active:
            return {"message": "invitation institution is inactive"}, 400
        expected_invite_hash = invite.code_hash

    user = User(
        username=username,
        email=email,
        phone=phone,
        role="institution_admin" if invite else "user",
        managed_institution_id=invite.institution_id if invite else None,
        health_id=None if invite else _new_health_id(),
    )
    user.set_password(password)
    try:
        db.session.add(user)
        db.session.flush()
        if invite is not None:
            consumed = db.session.execute(
                update(InstitutionInvite)
                .where(
                    InstitutionInvite.id == invite.id,
                    InstitutionInvite.code_hash == expected_invite_hash,
                    InstitutionInvite.status == "active",
                    InstitutionInvite.used_by_user_id.is_(None),
                )
                .values(
                    status="used",
                    used_by_user_id=user.id,
                    used_at=datetime.now(timezone.utc),
                )
                .execution_options(synchronize_session=False)
            )
            if consumed.rowcount != 1:
                db.session.rollback()
                return {"message": "invitation code has already been used"}, 409
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {"message": "注册信息冲突，请检查后重试"}, 409

    return _build_auth_payload(user, "register success"), 201


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    captcha_id = (payload.get("captcha_id") or "").strip()
    captcha_answer = (payload.get("captcha_answer") or "").strip()

    if not username or not password or not captcha_id or not captcha_answer:
        return {"message": "username, password and captcha are required"}, 400

    if not _verify_captcha(captcha_id, captcha_answer):
        return {"message": "invalid captcha"}, 400

    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        return {"message": "invalid username or password"}, 401
    if not user.is_active:
        return {"message": "account is inactive"}, 403
    if user.role == "institution_admin" and (
        user.managed_institution is None or not user.managed_institution.is_active
    ):
        return {"message": "institution is inactive"}, 403

    return _build_auth_payload(user, "login success"), 200


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh_token():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))
    if user is None:
        return {"message": "user not found"}, 404
    if not user.is_active:
        return {"message": "account is inactive"}, 403

    access_token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return {"access_token": access_token}, 200


@auth_bp.post("/logout")
@jwt_required()
def logout():
    return {"message": "logout success"}, 200

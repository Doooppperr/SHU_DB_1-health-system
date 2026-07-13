from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Institution, InstitutionImage, InstitutionInvite, User
from app.schema import SchemaUpgradeRequired, initialize_or_validate_schema


def _new_user(username: str, role: str, institution_id=None) -> User:
    user = User(
        username=username,
        role=role,
        managed_institution_id=institution_id,
    )
    user.set_password("secret123")
    return user


def test_institution_admin_binding_and_serialization(app):
    with app.app_context():
        institution = Institution.query.order_by(Institution.id).first()
        institution_admin = _new_user(
            "institution-manager",
            "institution_admin",
            institution.id,
        )
        db.session.add(institution_admin)
        db.session.commit()

        payload = institution_admin.to_dict()
        assert payload["role"] == "institution_admin"
        assert payload["managed_institution_id"] == institution.id
        assert payload["managed_institution"]["id"] == institution.id

        duplicate = _new_user(
            "duplicate-institution-manager",
            "institution_admin",
            institution.id,
        )
        db.session.add(duplicate)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


@pytest.mark.parametrize(
    ("role", "institution_id"),
    [
        ("institution_admin", None),
        ("user", "bound"),
        ("admin", "bound"),
    ],
)
def test_user_role_institution_binding_check(app, role, institution_id):
    with app.app_context():
        institution = Institution.query.order_by(Institution.id).first()
        resolved_institution_id = institution.id if institution_id == "bound" else None
        db.session.add(
            _new_user(
                f"invalid-{role}-{institution_id}",
                role,
                resolved_institution_id,
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_invite_is_one_current_row_per_institution_and_hash_is_private(app):
    with app.app_context():
        institution = Institution.query.order_by(Institution.id).first()
        admin = User.query.filter_by(role="admin").first()
        invite = InstitutionInvite(
            institution_id=institution.id,
            code_hash="a" * 64,
            status="active",
            issued_by_admin_id=admin.id,
        )
        db.session.add(invite)
        db.session.commit()

        payload = invite.to_dict()
        assert payload["institution_id"] == institution.id
        assert payload["status"] == "active"
        assert "code_hash" not in payload

        db.session.add(
            InstitutionInvite(
                institution_id=institution.id,
                code_hash="b" * 64,
                status="active",
                issued_by_admin_id=admin.id,
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_institution_image_order_constraints_and_cover_alias(app):
    with app.app_context():
        institution = Institution.query.order_by(Institution.id).first()
        institution.images.extend(
            [
                InstitutionImage(
                    storage_key="institutions/first.webp",
                    image_url="/uploads/institutions/first.webp",
                    sort_order=0,
                ),
                InstitutionImage(
                    storage_key="institutions/second.webp",
                    image_url="/uploads/institutions/second.webp",
                    sort_order=1,
                ),
            ]
        )
        db.session.commit()

        payload = institution.to_dict()
        assert payload["cover_image_url"] == "/uploads/institutions/first.webp"
        assert payload["logo_url"] == payload["cover_image_url"]
        assert [item["sort_order"] for item in payload["images"]] == [0, 1]
        assert payload["images"][0]["is_cover"] is True

        db.session.add(
            InstitutionImage(
                institution_id=institution.id,
                storage_key="institutions/ninth.webp",
                image_url="/uploads/institutions/ninth.webp",
                sort_order=8,
                created_at=datetime.now(timezone.utc),
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_schema_guard_rejects_incomplete_database_even_when_version_is_v2(app):
    with app.app_context():
        db.session.execute(text("DROP TABLE institution_images"))
        db.session.execute(text("PRAGMA user_version=2"))
        db.session.commit()

        with pytest.raises(SchemaUpgradeRequired, match="structure is incomplete"):
            initialize_or_validate_schema()

from datetime import datetime, timezone

import bcrypt

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.UniqueConstraint(
            "managed_institution_id",
            name="uq_users_managed_institution",
        ),
        db.CheckConstraint(
            "role in ('user', 'institution_admin', 'admin')",
            name="ck_users_role",
        ),
        db.CheckConstraint(
            "(role = 'institution_admin' and managed_institution_id is not null) "
            "or (role in ('user', 'admin') and managed_institution_id is null)",
            name="ck_users_role_institution_binding",
        ),
        db.CheckConstraint("length(trim(username)) > 0", name="ck_users_username_not_blank"),
    )

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    role = db.Column(db.String(20), default="user", nullable=False)
    managed_institution_id = db.Column(
        db.Integer,
        db.ForeignKey("institutions.id"),
        nullable=True,
        index=True,
    )
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    managed_institution = db.relationship(
        "Institution",
        back_populates="administrator",
        foreign_keys=[managed_institution_id],
        uselist=False,
    )
    issued_institution_invites = db.relationship(
        "InstitutionInvite",
        back_populates="issued_by_admin",
        foreign_keys="InstitutionInvite.issued_by_admin_id",
    )
    used_institution_invites = db.relationship(
        "InstitutionInvite",
        back_populates="used_by_user",
        foreign_keys="InstitutionInvite.used_by_user_id",
    )
    revoked_institution_invites = db.relationship(
        "InstitutionInvite",
        back_populates="revoked_by_admin",
        foreign_keys="InstitutionInvite.revoked_by_admin_id",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))

    def to_dict(self) -> dict:
        managed_institution = None
        if self.managed_institution is not None:
            managed_institution = {
                "id": self.managed_institution.id,
                "name": self.managed_institution.name,
                "branch_name": self.managed_institution.branch_name,
                "is_active": self.managed_institution.is_active,
            }

        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "phone": self.phone,
            "role": self.role,
            "managed_institution_id": self.managed_institution_id,
            "managed_institution": managed_institution,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

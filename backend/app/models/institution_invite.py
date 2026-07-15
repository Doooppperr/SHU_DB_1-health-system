from datetime import datetime, timezone

from app.extensions import db


def _utc_now():
    return datetime.now(timezone.utc)


class InstitutionInvite(db.Model):
    """The current institution-admin invitation for an institution.

    An institution owns at most one row. Reissuing a code updates that row and
    clears its previous use metadata, so the database never has two
    competing "current" codes for the same institution.
    """

    __tablename__ = "institution_invites"
    __table_args__ = (
        db.UniqueConstraint(
            "institution_id",
            name="uq_institution_invites_institution",
        ),
        db.UniqueConstraint(
            "code_hash",
            name="uq_institution_invites_code_hash",
        ),
        db.CheckConstraint(
            "status in ('active', 'used', 'superseded')",
            name="ck_institution_invites_status",
        ),
        db.CheckConstraint(
            "length(trim(code_hash)) > 0",
            name="ck_institution_invites_code_hash_not_blank",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(
        db.Integer,
        db.ForeignKey("institutions.id"),
        nullable=False,
        index=True,
    )
    code_hash = db.Column(db.String(128), nullable=False)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="active",
        server_default="active",
    )
    issued_by_admin_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    used_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    issued_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)

    institution = db.relationship("Institution", back_populates="invite")
    issued_by_admin = db.relationship(
        "User",
        back_populates="issued_institution_invites",
        foreign_keys=[issued_by_admin_id],
    )
    used_by_user = db.relationship(
        "User",
        back_populates="used_institution_invites",
        foreign_keys=[used_by_user_id],
    )

    def to_dict(self) -> dict:
        institution = None
        if self.institution is not None:
            institution = {
                "id": self.institution.id,
                "name": self.institution.name,
                "branch_name": self.institution.branch_name,
                "is_active": self.institution.is_active,
            }

        # code_hash is intentionally omitted: it is authentication material,
        # not an API field.
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "institution": institution,
            "status": self.status,
            "issued_by_admin_id": self.issued_by_admin_id,
            "used_by_user_id": self.used_by_user_id,
            "issued_at": self.issued_at.isoformat() if self.issued_at else None,
            "used_at": self.used_at.isoformat() if self.used_at else None,
        }

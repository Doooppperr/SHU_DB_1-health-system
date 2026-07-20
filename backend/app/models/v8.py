from datetime import datetime, timezone

from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class Organization(db.Model):
    __tablename__ = "organizations"
    __table_args__ = (
        db.CheckConstraint("length(trim(name)) > 0", name="ck_organizations_name_not_blank"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    service_features = db.Column(db.JSON, nullable=False, default=list, server_default="[]")
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    branches = db.relationship(
        "Institution",
        back_populates="organization",
        order_by="Institution.id.asc()",
    )

    def to_dict(self, *, include_branches=False):
        payload = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "service_features": list(self.service_features or []),
            "is_active": self.is_active,
            "branch_count": len(self.branches),
            "active_branch_count": sum(1 for branch in self.branches if branch.is_active),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_branches:
            payload["branches"] = [branch.to_dict() for branch in self.branches]
        return payload


class ReportAccessLog(db.Model):
    __tablename__ = "report_access_logs"
    __table_args__ = (
        db.CheckConstraint(
            "access_type in ('detail', 'asset')",
            name="ck_report_access_logs_type",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_institution_id = db.Column(
        db.Integer, db.ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    report_id = db.Column(
        db.Integer, db.ForeignKey("institution_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_institution_id = db.Column(
        db.Integer, db.ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    access_type = db.Column(db.String(20), nullable=False)
    accessed_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    actor = db.relationship("User", foreign_keys=[actor_user_id])
    actor_institution = db.relationship("Institution", foreign_keys=[actor_institution_id])
    source_institution = db.relationship("Institution", foreign_keys=[source_institution_id])
    report = db.relationship("InstitutionReport")

    def to_dict(self):
        return {
            "id": self.id,
            "actor": {
                "id": self.actor.id,
                "username": self.actor.username,
            } if self.actor else None,
            "actor_branch": {
                "id": self.actor_institution.id,
                "branch_name": self.actor_institution.branch_name,
            } if self.actor_institution else None,
            "report_id": self.report_id,
            "source_branch": {
                "id": self.source_institution.id,
                "branch_name": self.source_institution.branch_name,
            } if self.source_institution else None,
            "access_type": self.access_type,
            "accessed_at": self.accessed_at.isoformat() if self.accessed_at else None,
        }

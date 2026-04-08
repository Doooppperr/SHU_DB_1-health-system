from datetime import datetime, timezone

from app.extensions import db


class HealthRecord(db.Model):
    __tablename__ = "health_records"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    uploader_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    institution_id = db.Column(db.Integer, db.ForeignKey("institutions.id"), nullable=True, index=True)
    package_id = db.Column(db.Integer, db.ForeignKey("packages.id"), nullable=True)
    exam_date = db.Column(db.Date, nullable=False, index=True)
    report_file_url = db.Column(db.String(255), nullable=True)
    ocr_raw_text = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="confirmed")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    owner = db.relationship("User", foreign_keys=[owner_id])
    uploader = db.relationship("User", foreign_keys=[uploader_id])
    institution = db.relationship("Institution")
    package = db.relationship("Package")
    indicators = db.relationship(
        "HealthIndicator",
        back_populates="record",
        cascade="all, delete-orphan",
        order_by="HealthIndicator.id.asc()",
    )

    def to_dict(self, include_indicators=False):
        payload = {
            "id": self.id,
            "owner_id": self.owner_id,
            "uploader_id": self.uploader_id,
            "owner": {
                "id": self.owner.id,
                "username": self.owner.username,
            }
            if self.owner
            else None,
            "uploader": {
                "id": self.uploader.id,
                "username": self.uploader.username,
            }
            if self.uploader
            else None,
            "institution_id": self.institution_id,
            "package_id": self.package_id,
            "exam_date": self.exam_date.isoformat(),
            "report_file_url": self.report_file_url,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "institution": {
                "id": self.institution.id,
                "name": self.institution.name,
                "branch_name": self.institution.branch_name,
            }
            if self.institution
            else None,
            "package": {
                "id": self.package.id,
                "name": self.package.name,
            }
            if self.package
            else None,
            "indicator_count": len(self.indicators),
        }

        if include_indicators:
            payload["indicators"] = [item.to_dict() for item in self.indicators]

        return payload


class HealthIndicator(db.Model):
    __tablename__ = "health_indicators"
    __table_args__ = (
        db.UniqueConstraint("record_id", "indicator_dict_id", name="uq_record_indicator"),
    )

    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey("health_records.id"), nullable=False, index=True)
    indicator_dict_id = db.Column(db.Integer, db.ForeignKey("indicator_dicts.id"), nullable=False, index=True)
    value = db.Column(db.String(120), nullable=False)
    is_abnormal = db.Column(db.Boolean, nullable=False, default=False)
    source = db.Column(db.String(20), nullable=False, default="manual")

    record = db.relationship("HealthRecord", back_populates="indicators")
    indicator_dict = db.relationship("IndicatorDict", back_populates="indicators")

    def to_dict(self):
        return {
            "id": self.id,
            "record_id": self.record_id,
            "indicator_dict_id": self.indicator_dict_id,
            "value": self.value,
            "is_abnormal": self.is_abnormal,
            "source": self.source,
            "indicator": self.indicator_dict.to_dict() if self.indicator_dict else None,
        }

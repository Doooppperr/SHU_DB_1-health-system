from datetime import datetime, timezone

from app.extensions import db


class InstitutionImage(db.Model):
    __tablename__ = "institution_images"
    __table_args__ = (
        db.UniqueConstraint(
            "institution_id",
            "sort_order",
            name="uq_institution_images_sort_order",
        ),
        db.CheckConstraint(
            "sort_order between 0 and 7",
            name="ck_institution_images_sort_order",
        ),
        db.CheckConstraint(
            "length(trim(storage_key)) > 0",
            name="ck_institution_images_storage_key_not_blank",
        ),
        db.CheckConstraint(
            "length(trim(image_url)) > 0",
            name="ck_institution_images_url_not_blank",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(
        db.Integer,
        db.ForeignKey("institutions.id"),
        nullable=False,
        index=True,
    )
    storage_key = db.Column(db.String(255), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    institution = db.relationship("Institution", back_populates="images")

    def to_dict(self) -> dict:
        is_cover = self.sort_order == 0
        if self.institution is not None and self.institution.images:
            is_cover = self.institution.images[0] is self
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "image_url": self.image_url,
            "sort_order": self.sort_order,
            "is_cover": is_cover,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

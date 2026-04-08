from datetime import datetime, timezone

from app.extensions import db


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    institution_id = db.Column(db.Integer, db.ForeignKey("institutions.id"), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    is_visible = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User")
    institution = db.relationship("Institution")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "institution_id": self.institution_id,
            "content": self.content,
            "rating": self.rating,
            "is_visible": self.is_visible,
            "created_at": self.created_at.isoformat(),
            "user": {
                "id": self.user.id,
                "username": self.user.username,
            }
            if self.user
            else None,
            "institution": {
                "id": self.institution.id,
                "name": self.institution.name,
                "branch_name": self.institution.branch_name,
            }
            if self.institution
            else None,
        }

from datetime import datetime, timezone

from app.extensions import db


class FriendRelation(db.Model):
    __tablename__ = "friend_relations"
    __table_args__ = (
        db.UniqueConstraint("user_id", "friend_user_id", name="uq_friend_pair"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    friend_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    relation_name = db.Column(db.String(80), nullable=False, default="亲友")
    auth_status = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", foreign_keys=[user_id])
    friend_user = db.relationship("User", foreign_keys=[friend_user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "friend_user_id": self.friend_user_id,
            "relation_name": self.relation_name,
            "auth_status": self.auth_status,
            "created_at": self.created_at.isoformat(),
            "user": {
                "id": self.user.id,
                "username": self.user.username,
            }
            if self.user
            else None,
            "friend_user": {
                "id": self.friend_user.id,
                "username": self.friend_user.username,
            }
            if self.friend_user
            else None,
        }

import enum
from app import db


class NotificationStatus(enum.Enum):
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"


class DailyNotification(db.Model):
    __tablename__ = "daily_notifications"

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), primary_key=True)

    status = db.Column(db.Enum(NotificationStatus), nullable=False)

    title = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "status": self.status.value,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date.isoformat(),
            "prospect_id": self.prospect_id,
        }
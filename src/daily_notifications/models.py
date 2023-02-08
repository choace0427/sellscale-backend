import enum
from app import db


class NotificationStatus(enum.Enum):
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"


class DailyNotification(db.Model):
    __tablename__ = "daily_notifications"

    id = db.Column(db.Integer, primary_key=True)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=False)

    status = db.Column(db.Enum(NotificationStatus), nullable=False)

    title = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)

    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), nullable=True)

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
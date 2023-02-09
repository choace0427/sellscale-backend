import enum
from app import db


class NotificationStatus(enum.Enum):
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"

class NotificationType(enum.Enum):
    UNKNOWN = "UNKNOWN"
    UNREAD_MESSAGE = "UNREAD_MESSAGE"
    NEEDS_BUMP = "NEEDS_BUMP"
    SCHEDULING = "SCHEDULING"

class DailyNotification(db.Model):
    __tablename__ = "daily_notifications"

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), primary_key=True, default=-1)
    type = db.Column(db.Enum(NotificationType), primary_key=True, default=NotificationType.UNKNOWN)

    status = db.Column(db.Enum(NotificationStatus), nullable=False)

    title = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)

    __table_args__ = (db.PrimaryKeyConstraint('client_sdr_id', 'prospect_id', 'type'),)

    def to_dict(self):
        return {
            "client_sdr_id": self.client_sdr_id,
            "prospect_id": self.prospect_id,
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "due_date": self.due_date.isoformat(),
        }

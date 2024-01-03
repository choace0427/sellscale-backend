from app import db
import enum


class OperatorNotificationPriority(enum.Enum):
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    COMPLETED = 10


class OperatorNotificationType(enum.Enum):
    REVIEW_NEW_CAMPAIGN = "REVIEW_NEW_CAMPAIGN"
    DEMO_FEEDBACK_NEEDED = "DEMO_FEEDBACK_NEEDED"
    SCHEDULE_MEETING = "SCHEDULE_MEETING"


class OperatorNotification(db.Model):
    __tablename__ = "operator_notification"

    id = db.Column(db.Integer, primary_key=True)

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))

    title = db.Column(db.String, nullable=False)
    subtitle = db.Column(db.String, nullable=False)
    stars = db.Column(db.Integer, nullable=True)
    cta = db.Column(db.String, nullable=False)

    data = db.Column(db.JSON, nullable=False)

    notification_type = db.Column(db.Enum(OperatorNotificationType), nullable=False)
    priority = db.Column(db.Enum(OperatorNotificationPriority), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "title": self.title,
            "subtitle": self.subtitle,
            "stars": self.stars,
            "cta": self.cta,
            "data": self.data,
            "priority": self.priority,
        }

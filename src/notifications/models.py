from app import db
import enum


class OperatorNotificationPriority(enum.Enum):
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    COMPLETED = 10


class OperatorNotification(db.Model):
    __tablename__ = "operator_notification"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String, nullable=False)
    subtitle = db.Column(db.String, nullable=False)
    stars = db.Column(db.Integer, nullable=True)
    cta = db.Column(db.String, nullable=False)

    data = db.Column(db.JSON, nullable=False)

    priority = db.Column(db.Enum(OperatorNotificationPriority), nullable=False)

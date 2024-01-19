from app import db
from enum import Enum
from sqlalchemy.dialects.postgresql import JSONB


class SlackNotificationType(Enum):
    """The types of Slack notifications that can be sent"""

    AI_REPLY_TO_EMAIL = "AI_REPLY_TO_EMAIL"

    def name(self):
        return map_slack_notification_type_to_metadata[self].get("name")

    def description(self):
        return map_slack_notification_type_to_metadata[self].get("description")


map_slack_notification_type_to_metadata = {
    SlackNotificationType.AI_REPLY_TO_EMAIL: {
        "name": "AI Reply to Email",
        "description": "A Slack notification that is sent when the AI replies to an email",
    }
}


class SlackNotification(db.Model):
    __tablename__ = "slack_notification"

    id = db.Column(db.Integer, primary_key=True)

    notification_type = db.Column(
        db.Enum(SlackNotificationType), nullable=False, unique=True
    )
    notification_name = db.Column(db.String(255), nullable=False)
    notification_description = db.Column(db.String, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "notification_type": self.notification_type.value,
            "notification_name": self.notification_name,
            "notification_description": self.notification_description,
        }


class SentSlackNotification(db.Model):
    __tablename__ = "sent_slack_notification"

    id = db.Column(db.Integer, primary_key=True)

    # Who sent the notification
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)

    # What type of notification was sent
    notification_type = db.Column(db.Enum(SlackNotificationType), nullable=False)

    # What was the 'base' message
    message = db.Column(db.String, nullable=False)

    # Which webhook URL was sent to
    webhook_url = db.Column(JSONB, nullable=False)

    # What were the Slack notification blocks
    blocks = db.Column(db.ARRAY(JSONB), nullable=True)

    # If there was an error sending the notification, what was it?
    error = db.Column(db.String, nullable=True)


def populate_slack_notifications():
    """Populate the Slack notifications table with all of the Slack notifications"""
    for slack_notification_type in SlackNotificationType:
        # Get the Slack notification
        slack_notification = SlackNotification.query.filter_by(
            notification_type=slack_notification_type
        ).first()

        # If the Slack notification doesn't exist, then create it
        if not slack_notification:
            slack_notification = SlackNotification(
                notification_type=slack_notification_type,
                notification_name=slack_notification_type.name(),
                notification_description=slack_notification_type.description(),
            )
            db.session.add(slack_notification)
            db.session.commit()

from app import db
from enum import Enum
from sqlalchemy.dialects.postgresql import JSONB


class SlackNotificationType(Enum):
    """The types of Slack notifications that can be sent"""

    AI_REPLY_TO_EMAIL = "AI_REPLY_TO_EMAIL"

    def name(self):
        return get_slack_notification_type_metadata()[self].get("name")

    def description(self):
        return get_slack_notification_type_metadata()[self].get("description")

    def get_class(self):
        return get_slack_notification_type_metadata()[self].get("class")


def get_slack_notification_type_metadata():
    from src.slack.notifications.email_ai_reply_notification import (
        EmailAIReplyNotification,
    )

    map_slack_notification_type_to_metadata = {
        SlackNotificationType.AI_REPLY_TO_EMAIL: {
            "name": "AI Reply to Email",
            "description": "A Slack notification that is sent when the AI replies to an email",
            "class": EmailAIReplyNotification,
        }
    }

    return map_slack_notification_type_to_metadata


class SlackNotification(db.Model):  # type: ignore
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


class SentSlackNotification(db.Model):  # type: ignore
    __tablename__ = "sent_slack_notification"

    id = db.Column(db.Integer, primary_key=True)

    # Who sent the notification
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)

    # What type of notification was sent
    notification_type = db.Column(db.Enum(SlackNotificationType), nullable=False)

    # What was the 'base' message
    message = db.Column(db.String, nullable=False)

    # Which webhook URL was sent to
    webhook_url = db.Column(JSONB, nullable=True)

    # Which channel was the notification sent to
    slack_channel_id = db.Column(db.String(255), nullable=True)

    # What were the Slack notification blocks
    blocks = db.Column(db.ARRAY(JSONB), nullable=True)

    # If there was an error sending the notification, what was it?
    error = db.Column(db.String, nullable=True)


def populate_slack_notifications():
    """Populate the Slack notifications table with all of the Slack notifications. Should be called after introducing a new Slack notification type."""
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


def subscribe_all_sdrs_to_notification(notification_type: SlackNotificationType):
    """Subscribe all of the SDRs to a Slack notification type. Should be called after introducing a new Slack notification type."""
    from src.client.models import ClientSDR
    from src.subscriptions.services import subscribe_to_slack_notification

    # Get the ID of this notification type
    slack_notification: SlackNotification = SlackNotification.query.filter_by(
        notification_type=notification_type
    ).first()
    if not slack_notification:
        raise Exception(
            f"Slack notification of type: {notification_type.value} not found"
        )

    # Get all of the active SDRs
    client_sdrs: list[ClientSDR] = ClientSDR.query.filter_by(active=True).all()

    # Create subscriptions to this notification type for all of the SDRs
    for client_sdr in client_sdrs:
        subscribe_to_slack_notification(
            client_sdr_id=client_sdr.id, slack_notification_id=slack_notification.id
        )

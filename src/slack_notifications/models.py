from app import db
from sqlalchemy.dialects.postgresql import JSONB


class SentSlackNotification(db.Model):
    __tablename__ = "sent_slack_notification"

    id = db.Column(db.Integer, primary_key=True)

    # Who sent the notification
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)

    # What type of notification was sent (usually the name of the function that sent it)
    type = db.Column(db.String(255), nullable=False)

    # What was the 'base' message
    message = db.Column(db.String, nullable=False)

    # Which webhook URL was sent to
    webhook_url = db.Column(JSONB, nullable=False)

    # What were the Slack notification blocks
    blocks = db.Column(db.ARRAY(JSONB), nullable=True)

    # If there was an error sending the notification, what was it?
    error = db.Column(db.String, nullable=True)

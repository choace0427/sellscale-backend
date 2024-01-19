from app import db
from enum import Enum
from typing import TypedDict


class Subscription(db.Model):
    __tablename__ = "subscription"

    id = db.Column(db.Integer, primary_key=True)

    # Who is subscribed
    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=False
    )

    # Different subscription types
    slack_notification_id = db.Column(
        db.Integer, db.ForeignKey("slack_notification.id"), nullable=True
    )
    # TODO: Implement email_newsletter_id = db.Column(db.Integer, db.ForeignKey("email_newsletter.id"), nullable=True)

    active = db.Column(db.Boolean, nullable=False, default=True)
    deactivation_date = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "slack_notification_id": self.slack_notification_id,
            "active": self.active,
            "deactivation_date": self.deactivation_date,
        }

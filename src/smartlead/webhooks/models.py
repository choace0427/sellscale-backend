from app import db
from sqlalchemy.dialects.postgresql import JSONB
import enum


class SmartleadWebhookProcessingStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    INELIGIBLE = "INELIGIBLE"
    FAILED = "FAILED"


class SmartleadWebhookType(enum.Enum):
    EMAIL_SENT = "email.sent"
    EMAIL_OPENED = "email.opened"
    EMAIL_REPLIED = "email.replied"
    EMAIL_BOUNCED = "email.bounced"


class SmartleadWebhookPayloads(db.Model):
    __tablename__ = "smartlead_webhook_payloads"

    id = db.Column(db.Integer, primary_key=True)

    smartlead_payload = db.Column(JSONB, nullable=False)
    smartlead_webhook_type = db.Column(db.Enum(SmartleadWebhookType), nullable=False)

    processing_status = db.Column(
        db.Enum(SmartleadWebhookProcessingStatus),
        nullable=False,
        default=SmartleadWebhookProcessingStatus.PENDING,
    )
    processing_fail_reason = db.Column(db.String, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "smartlead_payload": self.smartlead_payload,
            "smartlead_webhook_type": self.smartlead_webhook_type.value,
            "processing_status": self.processing_status.value,
            "processing_fail_reason": self.processing_fail_reason,
        }

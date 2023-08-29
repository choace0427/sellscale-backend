import enum
from app import db


class NylasWebhookProcessingStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    INELIGIBLE = "INELIGIBLE"
    FAILED = "FAILED"

class NylasWebhookType(enum.Enum):
    MESSAGE_CREATED = "message.created"
    MESSAGE_OPENED = "message.opened"
    EVENT_CREATED = "event.created"
    EVENT_UPDATED = "event.updated"
    THREAD_REPLIED = "thread.replied"


class NylasWebhookPayloads(db.Model):
    __tablename__ = "nylas_webhook_payloads"

    id = db.Column(db.Integer, primary_key=True)

    nylas_payload = db.Column(db.JSON, nullable=False)
    nylas_webhook_type = db.Column(db.Enum(NylasWebhookType), nullable=False)

    processing_status = db.Column(db.Enum(NylasWebhookProcessingStatus), nullable=False, default=NylasWebhookProcessingStatus.PENDING)
    processing_fail_reason = db.Column(db.String, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "nylas_payload": self.nylas_payload,
            "nylas_webhook_type": self.nylas_webhook_type.value,
            "processing_status": self.processing_status.value,
            "processing_fail_reason": self.processing_fail_reason,
        }

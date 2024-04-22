import enum
from app import db
from sqlalchemy.dialects.postgresql import JSONB


class MergeWebhookProcessingStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    INELIGIBLE = "INELIGIBLE"
    FAILED = "FAILED"


class MergeWebhookType(enum.Enum):
    CRM_OPPORTUNITY_UPDATED = "opportunity.changed"


class MergeWebhookPayload(db.Model):
    __tablename__ = "merge_webhook_payload"

    id = db.Column(db.Integer, primary_key=True)

    merge_payload = db.Column(JSONB, nullable=False)
    merge_webhook_type = db.Column(db.Enum(MergeWebhookType), nullable=False)

    processing_status = db.Column(
        db.Enum(MergeWebhookProcessingStatus),
        nullable=False,
        default=MergeWebhookProcessingStatus.PENDING,
    )
    processing_fail_reason = db.Column(db.String, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "merge_payload": self.merge_payload,
            "merge_webhook_type": self.merge_webhook_type.value,
            "processing_status": self.processing_status.value,
            "processing_fail_reason": self.processing_fail_reason,
        }

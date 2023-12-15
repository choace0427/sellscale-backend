from app import db

from typing import Optional
from src.smartlead.webhooks.models import (
    SmartleadWebhookPayloads,
    SmartleadWebhookProcessingStatus,
    SmartleadWebhookType,
)


def create_smartlead_webhook_payload(
    smartlead_payload: dict,
    smartlead_webhook_type: SmartleadWebhookType,
    processing_status: Optional[
        SmartleadWebhookProcessingStatus
    ] = SmartleadWebhookProcessingStatus.PENDING,
    processing_fail_reason: Optional[str] = None,
) -> int:
    """Create a new SmartleadWebhookPayloads entry.

    Args:
        smartlead_payload (dict): The payload from the Smartlead webhook.
        smartlead_webhook_type (SmartleadWebhookType): The type of Smartlead webhook.
        processing_status (Optional[SmartleadWebhookProcessingStatus], optional): Whether or not the processing status should have a non-default value. Defaults to SmartleadWebhookProcessingStatus.PENDING.
        processing_fail_reason (Optional[str], optional): Whether or not the payload should be marked with a default failure reason. Defaults to None.

    Returns:
        int: The ID of the new SmartleadWebhookPayloads entry.
    """
    # Create a new SmartleadWebhookPayloads entry
    new_smartlead_payload = SmartleadWebhookPayloads(
        smartlead_payload=smartlead_payload,
        smartlead_webhook_type=smartlead_webhook_type,
        processing_status=processing_status,
        processing_fail_reason=processing_fail_reason,
    )
    db.session.add(new_smartlead_payload)
    db.session.commit()

    return new_smartlead_payload.id

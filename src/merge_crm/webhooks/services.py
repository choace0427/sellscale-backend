from app import db

from typing import Optional
from src.merge_crm.webhooks.models import (
    MergeWebhookPayload,
    MergeWebhookProcessingStatus,
    MergeWebhookType,
)


def create_merge_webhook_payload(
    merge_payload: dict,
    merge_webhook_type: MergeWebhookType,
    processing_status: Optional[
        MergeWebhookProcessingStatus
    ] = MergeWebhookProcessingStatus.PENDING,
    processing_fail_reason: Optional[str] = None,
) -> int:
    """Create a new MergeWebhookPayload entry.

    Args:
        merge_payload (dict): The payload from the Merge webhook.
        merge_webhook_type (MergeWebhookType): The type of Merge webhook.
        processing_status (Optional[MergeWebhookProcessingStatus], optional): Whether or not the processing status should have a non-default value. Defaults to MergeWebhookProcessingStatus.PENDING.
        processing_fail_reason (Optional[str], optional): Whether or not the payload should be marked with a default failure reason. Defaults to None.

    Returns:
        int: The ID of the new MergeWebhookPayload entry.
    """
    # Create a new MergeWebhookPayload entry
    new_merge_payload = MergeWebhookPayload(
        merge_payload=merge_payload,
        merge_webhook_type=merge_webhook_type,
        processing_status=processing_status,
        processing_fail_reason=processing_fail_reason,
    )
    db.session.add(new_merge_payload)
    db.session.commit()

    return new_merge_payload.id

from app import db, celery

from typing import Optional
from src.smartlead.webhooks.models import (
    SmartleadWebhookPayloads,
    SmartleadWebhookProcessingStatus,
    SmartleadWebhookType,
)
from datetime import datetime, timedelta


@celery.task
def rerun_stale_smartlead_webhooks() -> None:
    """Rerun all stale webhooks.

    Stale webhooks are defined as webhooks that:
    - Are in PENDING or PROCESSING
    - Was last updated more than 1 hour ago

    Likely causees for Stale webhooks:
    - The webhook processing task failed
    - Celery or Redis experienced a failure

    This function is intended to be run as a cron job.

    Returns:
        None
    """
    from src.smartlead.webhooks.email_bounced import process_email_bounce_webhook
    from src.smartlead.webhooks.email_link_clicked import (
        process_email_link_clicked_webhook,
    )
    from src.smartlead.webhooks.email_opened import process_email_opened_webhook
    from src.smartlead.webhooks.email_replied import process_email_replied_webhook
    from src.smartlead.webhooks.email_sent import process_email_sent_webhook

    # Map webhook types to their respective processors
    webhook_type_to_processor = {
        SmartleadWebhookType.EMAIL_SENT: process_email_sent_webhook,
        SmartleadWebhookType.EMAIL_OPENED: process_email_opened_webhook,
        SmartleadWebhookType.EMAIL_REPLIED: process_email_replied_webhook,
        SmartleadWebhookType.EMAIL_BOUNCED: process_email_bounce_webhook,
        SmartleadWebhookType.EMAIL_LINK_CLICKED: process_email_link_clicked_webhook,
    }

    # Get all stale webhooks
    stale_webhooks: list[
        SmartleadWebhookPayloads
    ] = SmartleadWebhookPayloads.query.filter(
        SmartleadWebhookPayloads.processing_status.in_(
            [
                SmartleadWebhookProcessingStatus.PENDING,
                SmartleadWebhookProcessingStatus.PROCESSING,
            ]
        ),
        SmartleadWebhookPayloads.updated_at < datetime.now() - timedelta(hours=1),
    ).all()

    # Rerun each stale webhook
    for webhook in stale_webhooks:
        webhook_type = webhook.smartlead_webhook_type
        processor: function = webhook_type_to_processor.get(webhook_type)
        if processor:
            processor.delay(webhook.id)

    return None


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

import json
from typing import Union

from src.client.services import populate_single_prospect_event
from app import db, celery
from src.automation.slack_notification import send_status_change_slack_block
from src.client.models import ClientSDR
from src.email_outbound.models import (
    EmailConversationMessage,
    EmailConversationThread,
    ProspectEmail,
    ProspectEmailOutreachStatus,
)
from src.email_outbound.services import update_prospect_email_outreach_status
from src.prospecting.models import Prospect, ProspectChannels

from src.prospecting.nylas.services import nylas_update_threads, nylas_get_messages
from src.prospecting.nylas.nylas_wrappers import wrapped_nylas_get_single_thread
from src.prospecting.services import calculate_prospect_overall_status
from src.webhooks.models import NylasWebhookPayloads, NylasWebhookProcessingStatus, NylasWebhookType
from src.webhooks.nylas.bounce_detection import is_email_bounced


def create_nylas_webhook_payload_entry(
    nylas_payload: dict,
    nylas_webhook_type: NylasWebhookType,
    processing_status: NylasWebhookProcessingStatus = NylasWebhookProcessingStatus.PENDING,
    processing_fail_reason: str = None,
) -> int:
    """ Creates a new NylasWebhookPayloads entry in the database.

    Args:
        nylas_payload (dict): The payload from the Nylas webhook notification.
        nylas_webhook_type (NylasWebhookType): The type of webhook notification.
        processing_status (NylasWebhookProcessingStatus, optional): The processing status of the webhook notification. Defaults to NylasWebhookProcessingStatus.PENDING.
        processing_fail_reason (str, optional): The reason why the webhook notification failed to process. Defaults to None.

    Returns:
        int: The ID of the new entry.
    """
    new_entry = NylasWebhookPayloads(
        nylas_payload=nylas_payload,
        nylas_webhook_type=nylas_webhook_type,
        processing_status=processing_status,
        processing_fail_reason=processing_fail_reason,
    )
    db.session.add(new_entry)
    db.session.commit()
    return new_entry.id

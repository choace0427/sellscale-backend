from typing import Union
from app import db, celery
from src.client.services import populate_single_prospect_event
from src.webhooks.models import NylasWebhookPayloads, NylasWebhookProcessingStatus

@celery.task(bind=True, max_retries=5)
def process_deltas_event_update(
    self, deltas: Union[list[dict], dict], payload_id: int
) -> tuple[bool, int]:
    """Process a list of deltas from a Nylas webhook notification.

    Args:
        deltas (Union[list[dict], dict]): A list of deltas from a Nylas webhook notification.
        payload_id (int): The ID of the NylasWebhookPayloads entry that contains the webhook original payload.

    Returns:
        tuple[bool, int]: A tuple containing a boolean indicating whether the deltas were processed successfully, and an integer indicating the number of deltas that were processed.
    """
    # Process deltas
    if type(deltas) == dict:
        process_single_event_update.apply_async(args=[deltas, payload_id])
        return True, 1

    for delta in deltas:
        # Processing the data might take awhile, so we should split it up into
        # multiple tasks, so that we don't block the Celery worker.
        process_single_event_update.apply_async(args=[delta, payload_id])

    return True, len(deltas)


@celery.task(bind=True, max_retries=5)
def process_single_event_update(self, delta: dict, payload_id: int) -> tuple[bool, str]:
    """Process a single `event.updated` delta from a Nylas webhook notification.

    Args:
        delta (dict): A single `event.updated` delta from a Nylas webhook notification.
        payload_id (int): The ID of the NylasWebhookPayloads entry that contains the webhook original payload.

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating whether the delta was processed successfully, and a string containing the id of the event that was processed, or an error message.
    """
    try:
        # Get payload and set it to "PROCESSING"
        nylas_payload: NylasWebhookPayloads = NylasWebhookPayloads.query.get(
            payload_id)
        if not nylas_payload:
            return False, "No payload found"
        nylas_payload.processing_status = NylasWebhookProcessingStatus.PROCESSING
        db.session.commit()

        account_id = delta.get("object_data", {}).get("account_id")
        event_id = delta.get("object_data", {}).get("id")
        if not account_id or not event_id:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "No account ID or event ID in delta"
            db.session.commit()
            return False, "No account ID or event ID in delta"

        success = populate_single_prospect_event(account_id, event_id)
        if success:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.SUCCEEDED
            db.session.commit()
            return True, "Successfully populated prospect event"
        else:
            nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
            nylas_payload.processing_fail_reason = "Failed to populate prospect event"
            db.session.commit()
            return False, "Failed to populate prospect event"
    except Exception as e:
        nylas_payload: NylasWebhookPayloads = NylasWebhookPayloads.query.get(
            payload_id)
        if not nylas_payload:
            return False, "No payload found"

        nylas_payload.processing_status = NylasWebhookProcessingStatus.FAILED
        nylas_payload.processing_fail_reason = str(e)
        db.session.commit()
        return False, str(e)

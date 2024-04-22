from app import db, celery
from src.merge_crm.models import ClientSyncCRM

from src.merge_crm.webhooks.models import (
    MergeWebhookPayload,
    MergeWebhookProcessingStatus,
    MergeWebhookType,
)
from src.merge_crm.webhooks.services import create_merge_webhook_payload
from src.prospecting.models import Prospect


def create_and_process_crm_opportunity_updated_payload(payload: dict) -> bool:
    """Creates and processes a Merge CRM opportunity updated payload.

    Args:
        payload (dict): The payload from the Merge CRM webhook.

    Returns:
        bool: Whether or not the payload was processed successfully.
    """
    # Create a new MergeWebhookPayload entry
    payload_id = create_merge_webhook_payload(
        merge_payload=payload,
        merge_webhook_type=MergeWebhookType.CRM_OPPORTUNITY_UPDATED,
    )
    if not payload_id:
        return False

    # Process the payload
    process_crm_opportunity_updated_webhook.apply_async(args=[payload_id])

    return True


@celery.task(max_retries=5)
def process_crm_opportunity_updated_webhook(payload_id: int):
    try:
        # Get payload and set it to "PROCESSING"
        merge_payload: MergeWebhookPayload = MergeWebhookPayload.query.get(payload_id)
        if not merge_payload:
            return False, "No payload found"
        merge_payload.processing_status = MergeWebhookProcessingStatus.PROCESSING
        db.session.commit()

        # Verify the payload is a opportunity.changed event
        payload = merge_payload.merge_payload
        hook = payload.get("hook", {})
        event_type: str = hook.get("event", "")
        if event_type.lower() != "opportunity.changed":
            merge_payload.processing_status = MergeWebhookProcessingStatus.FAILED
            merge_payload.processing_fail_reason = (
                "Event type is not 'opportunity.changed'"
            )
            db.session.commit()
            return False, "Event type is not 'opportunity.changed'"

        # Verify that we have this linked account in the database
        linked_account = payload.get("linked_account", {})
        linked_account_id = linked_account.get("id")
        if not linked_account_id:
            merge_payload.processing_status = MergeWebhookProcessingStatus.FAILED
            merge_payload.processing_fail_reason = (
                "No linked account ID found in payload"
            )
            db.session.commit()
            return False, "No linked account ID found in payload"
        client_sync_crm: ClientSyncCRM = ClientSyncCRM.query.filter(
            ClientSyncCRM.account_id == linked_account_id
        ).first()
        if not client_sync_crm:
            merge_payload.processing_status = MergeWebhookProcessingStatus.FAILED
            merge_payload.processing_fail_reason = (
                "No linked account found in the database"
            )
            db.session.commit()
            return False, "No linked account found in the database"

        # Get the opportunity ID that was updated
        data = payload.get("data", {})
        opportunity_id = data.get("id")
        if not opportunity_id:
            merge_payload.processing_status = MergeWebhookProcessingStatus.FAILED
            merge_payload.processing_fail_reason = "No opportunity ID found in payload"
            db.session.commit()
            return False, "No opportunity ID found in payload"

        # Get the Prospects that this opportunity is linked to
        prospects: list[Prospect] = Prospect.query.filter(
            Prospect.merge_opportunity_id == opportunity_id
        ).all()
        for prospect in prospects:
            # Update the contract size
            prospect.contract_size = data.get("amount")

        # Set the payload to "SUCCEEDED"
        merge_payload.processing_status = MergeWebhookProcessingStatus.SUCCEEDED
        db.session.commit()

        return True
    except Exception as e:
        merge_payload.processing_status = MergeWebhookProcessingStatus.FAILED
        merge_payload.processing_fail_reason = str(e)
        db.session.commit()
        raise e

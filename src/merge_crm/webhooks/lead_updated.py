from app import db, celery
from src.client.models import Client, ClientSDR
from src.merge_crm.models import ClientSyncCRM

from src.merge_crm.webhooks.models import (
    MergeWebhookPayload,
    MergeWebhookProcessingStatus,
    MergeWebhookType,
)
from src.merge_crm.webhooks.services import create_merge_webhook_payload
from src.prospecting.models import Prospect
from src.utils.slack import send_slack_message, URL_MAP


def create_and_process_crm_lead_updated_payload(payload: dict) -> bool:
    """Creates and processes a Merge CRM lead updated payload.

    Args:
        payload (dict): The payload from the Merge CRM webhook.

    Returns:
        bool: Whether or not the payload was processed successfully.
    """
    # Create a new MergeWebhookPayload entry
    payload_id = create_merge_webhook_payload(
        merge_payload=payload,
        merge_webhook_type=MergeWebhookType.CRM_LEAD_UPDATED,
    )
    if not payload_id:
        return False

    # Process the payload
    process_crm_lead_updated_webhook.apply_async(args=[payload_id])

    return True


@celery.task(max_retries=5)
def process_crm_lead_updated_webhook(payload_id: int):
    try:
        # Get payload and set it to "PROCESSING"
        merge_payload: MergeWebhookPayload = MergeWebhookPayload.query.get(payload_id)
        if not merge_payload:
            return False, "No payload found"
        merge_payload.processing_status = MergeWebhookProcessingStatus.PROCESSING
        db.session.commit()

        # Verify the payload is a lead.changed event
        payload = merge_payload.merge_payload
        hook = payload.get("hook", {})
        event_type: str = hook.get("event", "")
        if event_type.lower() != "lead.changed":
            merge_payload.processing_status = MergeWebhookProcessingStatus.FAILED
            merge_payload.processing_fail_reason = "Event type is not 'lead.changed'"
            db.session.commit()
            return False, "Event type is not 'lead.changed'"

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

        # Get the lead ID that was updated
        data = payload.get("data", {})
        lead_id = data.get("id")
        if not lead_id:
            merge_payload.processing_status = MergeWebhookProcessingStatus.FAILED
            merge_payload.processing_fail_reason = "No lead ID found in payload"
            db.session.commit()
            return False, "No lead ID found in payload"

        # Get the Prospect that this lead is linked to
        prospect: Prospect = Prospect.query.filter(
            Prospect.merge_lead_id == lead_id
        ).first()
        if not prospect:
            merge_payload.processing_status = MergeWebhookProcessingStatus.FAILED
            merge_payload.processing_fail_reason = "No prospects found for lead"
            db.session.commit()
            return False, "No prospects found for lead"

        # Update the account / contact ID if it has changed
        updated = False
        new_contact_id = data.get("converted_contact")
        new_account_id = data.get("converted_account")
        if (
            new_contact_id != prospect.merge_contact_id
            or new_account_id != prospect.merge_account_id
        ):
            updated = True
            prospect.merge_contact_id = new_contact_id
            prospect.merge_account_id = new_account_id
            db.session.commit()

        # Send a Slack message
        if updated:
            integration = linked_account.get("integration")
            sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
            client: Client = Client.query.get(sdr.client_id)
            send_slack_message(
                message=f"Lead converted to account/contact\nUser: {sdr.name} ({client.company})\nCRM: {integration}\n\nProspect: {prospect.full_name} (#{prospect.id})",
                webhook_urls=[URL_MAP["ops-alerts-opportunity-changed"]],
            )

        # Set the payload to "SUCCEEDED"
        merge_payload.processing_status = MergeWebhookProcessingStatus.SUCCEEDED
        db.session.commit()

        return True
    except Exception as e:
        merge_payload.processing_status = MergeWebhookProcessingStatus.FAILED
        merge_payload.processing_fail_reason = str(e)
        db.session.commit()
        raise e

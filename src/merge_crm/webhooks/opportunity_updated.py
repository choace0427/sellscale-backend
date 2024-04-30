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
        if not prospects:
            merge_payload.processing_status = MergeWebhookProcessingStatus.FAILED
            merge_payload.processing_fail_reason = "No prospects found for opportunity"
            db.session.commit()
            return False, "No prospects found for opportunity"

        # Update the contract size for each Prospect
        new_contract_size = data.get("amount")
        sdr: ClientSDR = ClientSDR.query.get(prospects[0].client_sdr_id)
        client: Client = Client.query.get(sdr.client_id)
        slack_alert_sent = False
        for prospect in prospects:
            if new_contract_size != prospect.contract_size:
                # Send a Slack message
                if not slack_alert_sent:
                    slack_alert_sent = True
                    integration = linked_account.get("integration")
                    opportunity = data.get("name")
                    prospect_contract_size = prospect.contract_size or 0
                    difference = new_contract_size - prospect_contract_size
                    difference_str = f"{'+' if difference > 0 else ''}${difference}"
                    send_slack_message(
                        f"Opportunity value changed in CRM.\nUser: {sdr.name}\nCompany: {client.company}\nCRM: {integration}\n\nOpportunity: {opportunity}\nProspect: {prospect.full_name}\nChange: ${prospect.contract_size} -> ${new_contract_size} ({difference_str})",
                        webhook_urls=[URL_MAP["ops-alerts-opportunity-changed"]],
                    )

                # Update the contract size
                prospect.contract_size = new_contract_size

        # Set the payload to "SUCCEEDED"
        merge_payload.processing_status = MergeWebhookProcessingStatus.SUCCEEDED
        db.session.commit()

        return True
    except Exception as e:
        merge_payload.processing_status = MergeWebhookProcessingStatus.FAILED
        merge_payload.processing_fail_reason = str(e)
        db.session.commit()
        raise e

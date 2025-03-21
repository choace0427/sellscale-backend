from app import db, celery
from src.client.models import ClientArchetype
from src.email_outbound.models import (
    ProspectEmail,
    ProspectEmailOutreachStatus,
    ProspectEmailStatus,
)
from src.prospecting.models import Prospect
from src.prospecting.services import update_prospect_status_email

from src.smartlead.webhooks.models import (
    SmartleadWebhookPayloads,
    SmartleadWebhookProcessingStatus,
    SmartleadWebhookType,
)
from src.smartlead.webhooks.services import create_smartlead_webhook_payload


def create_and_process_email_bounce_payload(payload: dict) -> bool:
    """Create a new SmartleadWebhookPayloads entry and process it.

    Args:
        payload (dict): The payload from the Smartlead webhook.

    Returns:
        bool: Whether or not the payload was processed successfully.
    """
    # Create a new SmartleadWebhookPayloads entry
    payload_id = create_smartlead_webhook_payload(
        smartlead_payload=payload,
        smartlead_webhook_type=SmartleadWebhookType.EMAIL_BOUNCED,
    )
    if not payload_id:
        return False

    # Process the payload
    process_email_bounce_webhook.apply_async(args=[payload_id])

    return True


@celery.task(max_retries=5)
def process_email_bounce_webhook(payload_id: int):
    try:
        # Get payload and set it to "PROCESSING"
        smartlead_payload: SmartleadWebhookPayloads = (
            SmartleadWebhookPayloads.query.get(payload_id)
        )
        if not smartlead_payload:
            return False, "No payload found"
        smartlead_payload.processing_status = (
            SmartleadWebhookProcessingStatus.PROCESSING
        )
        db.session.commit()

        # Verify the payload is an EMAIL_BOUNCE event
        payload: dict = smartlead_payload.smartlead_payload
        event_type = payload.get("event_type")
        if event_type != "EMAIL_BOUNCE":
            smartlead_payload.processing_status = (
                SmartleadWebhookProcessingStatus.FAILED
            )
            smartlead_payload.processing_fail_reason = (
                "Event type is not 'EMAIL_BOUNCE'"
            )
            db.session.commit()
            return False, "Event type is not 'EMAIL_BOUNCE'"

        # Get the email address that the email was bounce to
        to_email = payload.get("to_email")
        if not to_email:
            smartlead_payload.processing_status = (
                SmartleadWebhookProcessingStatus.FAILED
            )
            smartlead_payload.processing_fail_reason = "No 'to_email' field found"
            db.session.commit()
            return False, "No 'to_email' field found"

        # Get the campaign ID that the email was bounce from
        campaign_id = payload.get("campaign_id")
        if not campaign_id:
            smartlead_payload.processing_status = (
                SmartleadWebhookProcessingStatus.FAILED
            )
            smartlead_payload.processing_fail_reason = "No 'campaign_id' field found"
            db.session.commit()
            return False, "No 'campaign_id' field found"

        # Find the Archetype and Prospect using the above information
        client_archetype: ClientArchetype = ClientArchetype.query.filter_by(
            smartlead_campaign_id=campaign_id
        ).first()
        if not client_archetype:
            smartlead_payload.processing_status = (
                SmartleadWebhookProcessingStatus.FAILED
            )
            smartlead_payload.processing_fail_reason = "No Archetype found"
            db.session.commit()
            return False, "No Archetype found"
        prospect: Prospect = Prospect.query.filter_by(
            email=to_email, archetype_id=client_archetype.id
        ).first()
        if not prospect:
            smartlead_payload.processing_status = (
                SmartleadWebhookProcessingStatus.FAILED
            )
            smartlead_payload.processing_fail_reason = "No Prospect found"
            db.session.commit()
            return False, "No Prospect found"

        # Get the Prospect Email
        prospect_email: ProspectEmail = ProspectEmail.query.get(
            prospect.approved_prospect_email_id
        )
        if not prospect_email:
            smartlead_payload.processing_status = (
                SmartleadWebhookProcessingStatus.FAILED
            )
            smartlead_payload.processing_fail_reason = "No Prospect Email found"
            db.session.commit()
            return False, "No Prospect Email found"

        # Verify that the email was bounced
        is_bounced = payload.get("is_bounced")
        if not is_bounced:
            smartlead_payload.processing_status = (
                SmartleadWebhookProcessingStatus.FAILED
            )
            smartlead_payload.processing_fail_reason = "Email was not bounced"
            db.session.commit()
            return False, "Email was not bounced"

        # Set the Prospect Email to "bounce"
        update_prospect_status_email(
            prospect_id=prospect.id,
            new_status=ProspectEmailOutreachStatus.BOUNCED,
        )

        # TEMPORARY: Send slack notification
        from src.utils.slack import send_slack_message
        from src.utils.slack import URL_MAP

        send_slack_message(
            message=f"Smartlead Payload: Email to {prospect.full_name} ({prospect.email}) was bounced.",
            webhook_urls=[URL_MAP["eng-sandbox"]],
        )

        # Set the payload to "SUCCEEDED"
        smartlead_payload.processing_status = SmartleadWebhookProcessingStatus.SUCCEEDED
        db.session.commit()
    except Exception as e:
        smartlead_payload: SmartleadWebhookPayloads = (
            SmartleadWebhookPayloads.query.get(payload_id)
        )
        if not smartlead_payload:
            return False, "No payload found"

        smartlead_payload.processing_status = SmartleadWebhookProcessingStatus.FAILED
        smartlead_payload.processing_fail_reason = str(e)
        db.session.commit()
        return False, str(e)

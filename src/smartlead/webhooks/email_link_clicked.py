import re
from bs4 import BeautifulSoup
from app import db, celery
from src.client.models import ClientArchetype
from src.email_classifier.services import classify_email
from src.email_outbound.models import (
    ProspectEmail,
    ProspectEmailOutreachStatus,
    ProspectEmailStatus,
)
from src.prospecting.models import Prospect
from src.prospecting.services import update_prospect_status_email
from src.slack.notifications.email_link_clicked import EmailLinkClickedNotification
from src.smartlead.services import generate_smart_email_response

from src.smartlead.webhooks.models import (
    SmartleadWebhookPayloads,
    SmartleadWebhookProcessingStatus,
    SmartleadWebhookType,
)
from src.smartlead.webhooks.services import create_smartlead_webhook_payload
from src.utils.datetime.dateparse_utils import convert_string_to_datetime_or_none


def create_and_process_email_link_clicked_payload(payload: dict) -> bool:
    """Create a new SmartleadWebhookPayloads entry and process it.

    Args:
        payload (dict): The payload from the Smartlead webhook.

    Returns:
        bool: Whether or not the payload was processed successfully.
    """
    # Create a new SmartleadWebhookPayloads entry
    payload_id = create_smartlead_webhook_payload(
        smartlead_payload=payload,
        smartlead_webhook_type=SmartleadWebhookType.EMAIL_LINK_CLICKED,
    )
    if not payload_id:
        return False

    # Process the payload
    process_email_link_clicked_webhook.apply_async(args=[payload_id])

    return True


@celery.task(max_retries=5)
def process_email_link_clicked_webhook(payload_id: int):
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

        # Verify the payload is an EMAIL_LINK_CLICKED event
        payload: dict = smartlead_payload.smartlead_payload
        event_type = payload.get("event_type")
        if event_type != "EMAIL_LINK_CLICK":
            smartlead_payload.processing_status = (
                SmartleadWebhookProcessingStatus.FAILED
            )
            smartlead_payload.processing_fail_reason = (
                "Event type is not 'EMAIL_LINK_CLICK'"
            )
            db.session.commit()
            return False, "Event type is not 'EMAIL_LINK_CLICK'"

        # Get the email address that the email was replied to
        to_email = payload.get("to_email")
        if not to_email:
            smartlead_payload.processing_status = (
                SmartleadWebhookProcessingStatus.FAILED
            )
            smartlead_payload.processing_fail_reason = "No 'to_email' field found"
            db.session.commit()
            return False, "No 'to_email' field found"

        # Get the campaign ID that the email was replied from
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

        # Set the Prospect Email to "ACCEPTED"
        update_prospect_status_email(
            prospect_id=prospect.id,
            new_status=ProspectEmailOutreachStatus.ACCEPTED,
        )

        # Send a Slack Notification
        notification = EmailLinkClickedNotification(
            client_sdr_id=prospect.client_sdr_id,
            prospect_id=prospect.id,
            link_clicked=payload.get("link_details")[0],
        )
        success = notification.send_notification(preview_mode=False)

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
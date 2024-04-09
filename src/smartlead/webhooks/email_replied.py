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
from src.email_scheduling.models import EmailMessagingSchedule
from src.email_sequencing.models import EmailSequenceStep
from src.prospecting.models import Prospect
from src.prospecting.services import update_prospect_status_email
from src.smartlead.services import generate_smart_email_response

from src.smartlead.webhooks.models import (
    SmartleadWebhookPayloads,
    SmartleadWebhookProcessingStatus,
    SmartleadWebhookType,
)
from src.smartlead.webhooks.services import create_smartlead_webhook_payload
from src.utils.datetime.dateparse_utils import convert_string_to_datetime_or_none


def create_and_process_email_replied_payload(payload: dict) -> bool:
    """Create a new SmartleadWebhookPayloads entry and process it.

    Args:
        payload (dict): The payload from the Smartlead webhook.

    Returns:
        bool: Whether or not the payload was processed successfully.
    """
    # Create a new SmartleadWebhookPayloads entry
    payload_id = create_smartlead_webhook_payload(
        smartlead_payload=payload,
        smartlead_webhook_type=SmartleadWebhookType.EMAIL_REPLIED,
    )
    if not payload_id:
        return False

    # Process the payload
    process_email_replied_webhook.apply_async(args=[payload_id])

    return True


@celery.task(max_retries=5)
def process_email_replied_webhook(payload_id: int):
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

        # Verify the payload is an EMAIL_REPLY event
        payload: dict = smartlead_payload.smartlead_payload
        event_type = payload.get("event_type")
        if event_type != "EMAIL_REPLY":
            smartlead_payload.processing_status = (
                SmartleadWebhookProcessingStatus.FAILED
            )
            smartlead_payload.processing_fail_reason = "Event type is not 'EMAIL_REPLY'"
            db.session.commit()
            return False, "Event type is not 'EMAIL_REPLY'"

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

        # Get the email that was sent and email that was replied
        sent_message: dict = payload.get("sent_message")
        sent_message = sent_message.get("text")
        sent_message = re.sub("\n+", "\n", sent_message)
        sent_message = sent_message.strip("\n")

        reply_message: dict = payload.get("reply_message")
        reply_message = reply_message.get("text")
        reply_message = re.sub("\n+", "\n", reply_message)
        reply_message = reply_message.strip("\n")

        metadata = {
            "prospect_email": prospect.email,
            "email_sent_subject": payload.get("subject"),
            "email_sent_body": sent_message,
            "email_reply_body": reply_message,
        }

        # ANALYTICS
        if "ACTIVE_CONVO" not in prospect_email.outreach_status.value:
            # Cascading Replies: Get all the email schedule entries up to prospect_email.smartlead_sent_count entries
            sent_emails: list[EmailMessagingSchedule] = (
                EmailMessagingSchedule.query.filter(
                    EmailMessagingSchedule.prospect_email_id == prospect_email.id,
                )
                .order_by(EmailMessagingSchedule.created_at.asc())
                .limit(prospect_email.smartlead_sent_count)
                .all()
            )
            for email in sent_emails:
                template: EmailSequenceStep = EmailSequenceStep.query.get(
                    email.email_body_template_id
                )
                if template:
                    if template.times_replied is None:
                        template.times_replied = 0
                    template.times_replied += 1

        # Set the Prospect Email to "ACTIVE_CONVO"
        update_prospect_status_email(
            prospect_id=prospect.id,
            new_status=ProspectEmailOutreachStatus.ACTIVE_CONVO,
            metadata=metadata,
        )

        # Set the prospect_email's last_message and last_reply_time
        prospect_email.last_message = reply_message
        prospect.email_last_message_from_prospect = reply_message
        reply_time = payload.get("reply_message").get("time")
        reply_time = convert_string_to_datetime_or_none(content=reply_time)
        prospect_email.last_reply_time = reply_time
        prospect.email_last_message_timestamp = reply_time

        # Clear out any hidden_until and hidden_reason
        prospect_email.hidden_until = None
        prospect.hidden_until = None
        prospect.hidden_reason = None

        # Generate an automated reply
        generate_smart_email_response(
            client_sdr_id=prospect.client_sdr_id,
            prospect_id=prospect.id,
        )

        # Determine "ACTIVE_CONVO" substatus
        _ = classify_email.delay(
            prospect_id=prospect.id,
            email_body=reply_message,
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

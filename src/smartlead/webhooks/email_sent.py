from app import db, celery
import datetime
from src.client.models import ClientArchetype
from src.email_outbound.models import (
    ProspectEmail,
    ProspectEmailOutreachStatus,
    ProspectEmailStatus,
)
from src.email_scheduling.models import EmailMessagingSchedule, EmailMessagingType
from src.email_sequencing.models import EmailSequenceStep, EmailSubjectLineTemplate
from src.message_generation.models import GeneratedMessage, GeneratedMessageStatus
from src.prospecting.models import Prospect
from src.prospecting.services import update_prospect_status_email

from src.smartlead.webhooks.models import (
    SmartleadWebhookPayloads,
    SmartleadWebhookProcessingStatus,
    SmartleadWebhookType,
)
from src.smartlead.webhooks.services import create_smartlead_webhook_payload
from sqlalchemy import or_


def create_and_process_email_sent_payload(payload: dict) -> bool:
    """Create a new SmartleadWebhookPayloads entry and process it.

    Args:
        payload (dict): The payload from the Smartlead webhook.

    Returns:
        bool: Whether or not the payload was processed successfully.
    """
    # Create a new SmartleadWebhookPayloads entry
    payload_id = create_smartlead_webhook_payload(
        smartlead_payload=payload,
        smartlead_webhook_type=SmartleadWebhookType.EMAIL_SENT,
    )
    if not payload_id:
        return False

    # Process the payload
    process_email_sent_webhook.apply_async(args=[payload_id])

    return True


@celery.task(max_retries=5)
def process_email_sent_webhook(payload_id: int):
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

        # Verify the payload is an EMAIL_SENT event
        payload: dict = smartlead_payload.smartlead_payload
        event_type = payload.get("event_type")
        if event_type != "EMAIL_SENT":
            smartlead_payload.processing_status = (
                SmartleadWebhookProcessingStatus.FAILED
            )
            smartlead_payload.processing_fail_reason = "Event type is not 'EMAIL_SENT'"
            db.session.commit()
            return False, "Event type is not 'EMAIL_SENT'"

        # Get the email address that the email was sent to
        to_email = payload.get("to_email")
        if not to_email:
            smartlead_payload.processing_status = (
                SmartleadWebhookProcessingStatus.FAILED
            )
            smartlead_payload.processing_fail_reason = "No 'to_email' field found"
            db.session.commit()
            return False, "No 'to_email' field found"

        # Get the campaign ID that the email was sent from
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
        prospect: Prospect = Prospect.query.filter(
            Prospect.email.ilike(to_email),
            or_(
                Prospect.smartlead_campaign_id == campaign_id,
                Prospect.archetype_id == client_archetype.id,
            ),
            Prospect.approved_prospect_email_id.isnot(None)
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
        
        if payload.get("sent_message", {}).get("text"):
            #set the message text to the last message from the sdr
            prospect.email_last_message_from_sdr = payload.get("sent_message", {}).get("text")
            db.session.commit()

        # ANALYTICS: Update the Prospect Email smartlead_sent_count.
        if not prospect_email.smartlead_sent_count:
            prospect_email.smartlead_sent_count = 0
        prospect_email.smartlead_sent_count += 1

        # Set the Prospect Email to "SENT"
        now = datetime.datetime.now()
        update_prospect_status_email(
            prospect_id=prospect.id,
            new_status=ProspectEmailOutreachStatus.SENT_OUTREACH,
        )
        prospect_email.email_status = ProspectEmailStatus.SENT
        prospect_email.date_sent = now
        db.session.commit()

        # Save the Smartlead Campaign ID onto the Prospect
        prospect.smartlead_campaign_id = campaign_id
        db.session.commit()

        # ANALYTICS: Perform increments on the sequence steps
        if prospect_email.smartlead_sent_count:
            # If we've only sent 1 email, then we can assume its the first email
            if prospect_email.smartlead_sent_count == 1:
                subject_line: GeneratedMessage = GeneratedMessage.query.get(
                    prospect_email.personalized_subject_line
                )
                if subject_line:
                    subject_line.date_sent = now
                    subject_line.message_status = GeneratedMessageStatus.SENT
                    # ANALYTICS: Update the times_used count for the EmailSubjectLineTemplate
                    template: EmailSubjectLineTemplate = (
                        EmailSubjectLineTemplate.query.get(
                            subject_line.email_subject_line_template_id
                        )
                    )
                    if template:
                        template.times_used += 1
                body: GeneratedMessage = GeneratedMessage.query.get(
                    prospect_email.personalized_body
                )
                if body:
                    body.date_sent = now
                    body.message_status = GeneratedMessageStatus.SENT
                    # ANALYTICS: Update the times_used count for the EmailSequenceStep
                    template: EmailSequenceStep = EmailSequenceStep.query.get(
                        body.email_sequence_step_template_id
                    )
                    if template:
                        template.times_used += 1
            # Otherwise we need to get the smartlead_sent_count'th item in the schedule
            else:
                nth_item: EmailMessagingSchedule = (
                    EmailMessagingSchedule.query.filter_by(
                        prospect_email_id=prospect_email.id,
                    )
                    .order_by(EmailMessagingSchedule.id.asc())
                    .limit(prospect_email.smartlead_sent_count)
                    .all()
                )
                if nth_item:
                    nth_item = nth_item[-1]
                if (
                    nth_item
                    and nth_item.email_type == EmailMessagingType.FOLLOW_UP_EMAIL
                ):
                    nth_item.date_sent = now
                    template: EmailSequenceStep = EmailSequenceStep.query.get(
                        nth_item.email_body_template_id
                    )
                    if template:
                        template.times_used += 1
        db.session.commit()

        # TEMPORARY: Send slack notification
        from src.utils.slack import send_slack_message
        from src.utils.slack import URL_MAP

        send_slack_message(
            message=f"Smartlead Payload: Email sent to {prospect.full_name} ({prospect.email})",
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


def backfill():
    """Backfill all the EMAIL_SENT events."""
    payloads = SmartleadWebhookPayloads.query.filter_by(
        smartlead_webhook_type=SmartleadWebhookType.EMAIL_SENT,
        processing_status=SmartleadWebhookProcessingStatus.FAILED,
    ).all()

    from tqdm import tqdm

    for payload in tqdm(payloads):
        process_email_sent_webhook(payload_id=payload.id)
    return True

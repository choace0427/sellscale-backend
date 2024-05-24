from app import db, celery
from src.client.models import ClientArchetype
from src.email_outbound.models import (
    ProspectEmail,
    ProspectEmailOutreachStatus,
    ProspectEmailStatus,
)
from src.email_scheduling.models import EmailMessagingSchedule
from src.email_sequencing.models import EmailSequenceStep, EmailSubjectLineTemplate
from src.message_generation.models import GeneratedMessage
from src.prospecting.models import Prospect
from src.prospecting.services import update_prospect_status_email

from src.smartlead.webhooks.models import (
    SmartleadWebhookPayloads,
    SmartleadWebhookProcessingStatus,
    SmartleadWebhookType,
)
from src.smartlead.webhooks.services import create_smartlead_webhook_payload
from src.analytics.services import add_activity_log
from sqlalchemy import or_


def create_and_process_email_opened_payload(payload: dict) -> bool:
    """Create a new SmartleadWebhookPayloads entry and process it.

    Args:
        payload (dict): The payload from the Smartlead webhook.

    Returns:
        bool: Whether or not the payload was processed successfully.
    """
    # Create a new SmartleadWebhookPayloads entry
    payload_id = create_smartlead_webhook_payload(
        smartlead_payload=payload,
        smartlead_webhook_type=SmartleadWebhookType.EMAIL_OPENED,
    )
    if not payload_id:
        return False

    # Process the payload
    process_email_opened_webhook.apply_async(args=[payload_id])

    return True


@celery.task(max_retries=5)
def process_email_opened_webhook(payload_id: int):
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

        # Verify the payload is an EMAIL_OPENED event
        payload: dict = smartlead_payload.smartlead_payload
        event_type = payload.get("event_type")
        if event_type != "EMAIL_OPEN":
            smartlead_payload.processing_status = (
                SmartleadWebhookProcessingStatus.FAILED
            )
            smartlead_payload.processing_fail_reason = "Event type is not 'EMAIL_OPEN'"
            db.session.commit()
            return False, "Event type is not 'EMAIL_OPENED'"

        # Get the email address that the email was opened to
        to_email = payload.get("to_email")
        if not to_email:
            smartlead_payload.processing_status = (
                SmartleadWebhookProcessingStatus.FAILED
            )
            smartlead_payload.processing_fail_reason = "No 'to_email' field found"
            db.session.commit()
            return False, "No 'to_email' field found"

        # Get the campaign ID that the email was opened from
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

        # ANALYTICS
        if prospect_email.outreach_status == ProspectEmailOutreachStatus.SENT_OUTREACH:
            subject_line: GeneratedMessage = GeneratedMessage.query.get(
                prospect_email.personalized_subject_line
            )
            if subject_line:
                subject_line_template: EmailSubjectLineTemplate = (
                    EmailSubjectLineTemplate.query.get(
                        subject_line.email_subject_line_template_id
                    )
                )
                if subject_line_template:
                    if subject_line_template.times_accepted is None:
                        subject_line_template.times_accepted = 0
                    subject_line_template.times_accepted += 1

            # Cascading Opens: Get all the email schedule entries up to prospect_email.smartlead_sent_count entries
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
                    if template.times_accepted is None:
                        template.times_accepted = 0
                    template.times_accepted += 1

        try:
            # Set the Prospect Email to "OPENED"
            update_prospect_status_email(
                prospect_id=prospect.id,
                new_status=ProspectEmailOutreachStatus.EMAIL_OPENED,
            )
        except:
            # If the update fails, then something had gone wrong earlier. We skip for now
            pass

        # TEMPORARY: Send slack notification
        from src.utils.slack import send_slack_message
        from src.utils.slack import URL_MAP

        send_slack_message(
            message=f"Smartlead Payload: {prospect.full_name} ({prospect.email}) opened your email.",
            webhook_urls=[URL_MAP["eng-sandbox"]],
        )

        # Add an activity log
        add_activity_log(
            client_sdr_id=prospect.client_sdr_id,
            type="EMAIL-OPENED",
            name="Email Opened",
            description=f"{prospect.full_name} ({prospect.email}) opened your email.",
        )

        # Add engagement feed item
        from src.daily_notifications.services import (
            EngagementFeedType,
            create_engagement_feed_item,
        )
        from src.prospecting.models import ProspectChannels

        create_engagement_feed_item(
            client_sdr_id=prospect.client_sdr_id,
            prospect_id=prospect.id,
            channel_type=ProspectChannels.EMAIL.value,
            engagement_type=EngagementFeedType.EMAIL_OPENED.value,
            viewed=False,
            engagement_metadata={},
        )

        # Set the payload to "SUCCEEDED"
        print(f"Processed EMAIL_OPENED payload (#{smartlead_payload.id}) successfully")
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
    """Backfill all the EMAIL_OPENED events."""
    payloads = SmartleadWebhookPayloads.query.filter_by(
        smartlead_webhook_type=SmartleadWebhookType.EMAIL_OPENED,
        processing_status=SmartleadWebhookProcessingStatus.FAILED,
    ).all()

    from tqdm import tqdm

    for payload in tqdm(payloads):
        print(process_email_opened_webhook(payload_id=payload.id))
    return True

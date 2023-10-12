from app import celery, db

from datetime import datetime, timedelta
from typing import Optional
from src.client.models import ClientArchetype
from src.email_outbound.models import ProspectEmail, ProspectEmailOutreachStatus, ProspectEmailStatus
from src.email_scheduling.models import EmailMessagingSchedule, EmailMessagingType, EmailMessagingStatus
from src.email_sequencing.models import EmailSequenceStep
from src.message_generation.models import GeneratedMessage, GeneratedMessageStatus
from src.prospecting.models import Prospect, ProspectOverallStatus


FOLLOWUP_LIMIT = 10
DEFAULT_SENDING_DELAY_INTERVAL = 3


def create_email_messaging_schedule_entry(
    client_sdr_id: int,
    prospect_email_id: int,
    email_type: EmailMessagingType,
    email_body_template_id: int,
    send_status: EmailMessagingStatus,
    date_scheduled: datetime,
    email_subject_line_template_id: Optional[int] = None,
    subject_line_id: Optional[int] = None,
    body_id: Optional[int] = None,
) -> int:
    """ Creates an email_messaging_schedule entry in the database

    Args:
        client_sdr_id (int): ID of the client_sdr
        prospect_email_id (int): ID of the prospect_email
        email_type (EmailMessagingType): The type of email
        email_body_template_id (int): Body template ID
        send_status (EmailMessagingStatus): The status of the email
        date_scheduled (datetime): The date the email is scheduled to be sent
        email_subject_line_template_id (Optional[int], optional): The ID of the subject line template. Defaults to None.
        subject_line_id (Optional[int], optional): The ID of the subject line generation. Defaults to None.
        body_id (Optional[int], optional): The ID of the email body generation. Defaults to None.

    Returns:
        int: The ID of the created email_messaging_schedule entry
    """
    email_messaging_schedule: EmailMessagingSchedule = EmailMessagingSchedule(
        client_sdr_id=client_sdr_id,
        prospect_email_id=prospect_email_id,
        email_type=email_type,
        email_subject_line_template_id=email_subject_line_template_id,
        email_body_template_id=email_body_template_id,
        send_status=send_status,
        date_scheduled=date_scheduled,
        subject_line_id=subject_line_id,
        body_id=body_id,
    )
    db.session.add(email_messaging_schedule)
    db.session.commit()

    return email_messaging_schedule.id


def populate_email_messaging_schedule_entries(
    client_sdr_id: int,
    prospect_email_id: int,
    subject_line_id: int,
    body_id: int,
    initial_email_subject_line_template_id: int,
    initial_email_body_template_id: int,
    initial_email_send_date: datetime,
) -> list[int]:
    # Get the Archetype ID from the prospect
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    prospect: Prospect = Prospect.query.get(prospect_email.prospect_id)

    # Track all the scheduled email ids
    email_ids = []

    # Create the initial email entry
    initial_email_id = create_email_messaging_schedule_entry(
        client_sdr_id=client_sdr_id,
        prospect_email_id=prospect_email_id,
        email_type=EmailMessagingType.INITIAL_EMAIL,
        email_subject_line_template_id=initial_email_subject_line_template_id,
        email_body_template_id=initial_email_body_template_id,
        send_status=EmailMessagingStatus.SCHEDULED,
        date_scheduled=initial_email_send_date,
        subject_line_id=subject_line_id,
        body_id=body_id,
    )
    email_ids.append(initial_email_id)

    # Find the ACCEPTED sequence step
    accepted_sequence_step: EmailSequenceStep = EmailSequenceStep.query.filter_by(
        client_sdr_id=client_sdr_id,
        client_archetype_id=prospect.archetype_id,
        overall_status=ProspectOverallStatus.ACCEPTED,
    ).first()
    if not accepted_sequence_step:
        return email_ids

    # Create the accepted (1 time) followup
    accepted_followup_email_send_date = initial_email_send_date + \
        timedelta(days=DEFAULT_SENDING_DELAY_INTERVAL)
    accepted_followup_email_id = create_email_messaging_schedule_entry(
        client_sdr_id=client_sdr_id,
        prospect_email_id=prospect_email_id,
        email_type=EmailMessagingType.FOLLOW_UP_EMAIL,
        subject_line_id=None,
        body_id=None,
        email_subject_line_template_id=None,
        email_body_template_id=accepted_sequence_step.id,
        send_status=EmailMessagingStatus.NEEDS_GENERATION,
        date_scheduled=accepted_followup_email_send_date,
    )
    email_ids.append(accepted_followup_email_id)

    # Create the followups
    followups_created = 1
    followup_email_send_date = accepted_followup_email_send_date
    while followups_created < FOLLOWUP_LIMIT:  # 10 followups max
        # Search for a sequence step that is bumped and has a followup number
        bumped_sequence_step: EmailSequenceStep = EmailSequenceStep.query.filter_by(
            client_sdr_id=client_sdr_id,
            client_archetype_id=prospect.archetype_id,
            bumped_count=followups_created,
        ).first()
        if not bumped_sequence_step:
            break

        followup_email_send_date = followup_email_send_date + \
            timedelta(days=DEFAULT_SENDING_DELAY_INTERVAL)
        followup_email_id = create_email_messaging_schedule_entry(
            client_sdr_id=client_sdr_id,
            prospect_email_id=prospect_email_id,
            email_type=EmailMessagingType.FOLLOW_UP_EMAIL,
            email_body_template_id=bumped_sequence_step.id,
            send_status=EmailMessagingStatus.NEEDS_GENERATION,
            date_scheduled=followup_email_send_date,
            email_subject_line_template_id=None,
            subject_line_id=None,
            body_id=None,
        )
        email_ids.append(followup_email_id)
        followups_created += 1

    return email_ids


def collect_and_generate_email_messaging_schedule_entries() -> tuple[bool, str]:
    """ Collects and generates email_messaging_schedule entries that need to be generated

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating success and a message
    """
    # TODO: Increase limit
    # Get the first email_messaging_schedule entry that need to be generated
    email_messaging_schedule: EmailMessagingSchedule = EmailMessagingSchedule.query.filter(
        EmailMessagingSchedule.send_status == EmailMessagingStatus.NEEDS_GENERATION,
        EmailMessagingSchedule.date_scheduled <= datetime.utcnow() + timedelta(days=1),
    ).first()

    success, message = generate_email_messaging_schedule_entry.delay(
        email_messaging_schedule_id=email_messaging_schedule.id,
    )

    return success, message


@celery.task(bind=True, max_retries=3)
def generate_email_messaging_schedule_entry(
    self,
    email_messaging_schedule_id: int,
) -> tuple[bool, str]:
    """ Generates an email_messaging_schedule entry

    Args:
        email_messaging_schedule_id (int): The ID of the email_messaging_schedule entry to generate

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating success and a message
    """
    from src.message_generation.email.services import ai_followup_email_prompt, generate_email

    # Get the email_messaging_schedule entry
    email_messaging_schedule: EmailMessagingSchedule = EmailMessagingSchedule.query.get(
        email_messaging_schedule_id)
    if not email_messaging_schedule:
        return False, f"EmailMessagingSchedule with ID {email_messaging_schedule_id} does not exist"
    if email_messaging_schedule.send_status != EmailMessagingStatus.NEEDS_GENERATION:
        return False, f"EmailMessagingSchedule with ID {email_messaging_schedule_id} is not in NEEDS_GENERATION status"

    # Generate the email
    # 1. Get the prospect email
    prospect_email: ProspectEmail = ProspectEmail.query.get(
        email_messaging_schedule.prospect_email_id)

    # 2. Create the subject line
    # 2a. Get the subject line from the latest send
    last_messaging_schedule: EmailMessagingSchedule = EmailMessagingSchedule.query.filter(
        EmailMessagingSchedule.prospect_email_id == prospect_email.id,
        EmailMessagingSchedule.subject_line_id != None
    ).order_by(EmailMessagingSchedule.id.desc()).first()
    subject_line: GeneratedMessage = GeneratedMessage.query.get(
        last_messaging_schedule.subject_line_id)
    subject_line_text: str = subject_line.completion

    # 2b. Create the subject line
    reply_subject_line_text = f"Re: {subject_line_text}"
    reply_subject_line: GeneratedMessage = GeneratedMessage(
        prompt="Hardcoded: Reply Subject Line",
        completion=reply_subject_line_text,
        message_status=GeneratedMessageStatus.QUEUED_FOR_OUTREACH,
    )
    db.session.add(reply_subject_line)
    db.session.commit()

    # 2c. Attach the subject line to the email_messaging_schedule
    email_messaging_schedule.subject_line_id = reply_subject_line.id

    # 3. Create the email body
    # 3a. Get the past email bodies
    # past_email_bodies: list[EmailMessagingSchedule] = EmailMessagingSchedule.query.filter(
    #     EmailMessagingSchedule.prospect_email_id == prospect_email.id,
    #     EmailMessagingSchedule.body_id != None
    # ).order_by(EmailMessagingSchedule.id.asc()).all()

    # # 3b. Get the messages from the past email bodies
    # past_email_bodies_messages: list[GeneratedMessage] = []
    # for past_email_body in past_email_bodies:
    #     past_email_bodies_messages.append(GeneratedMessage.query.get(past_email_body.body_id))

    # 3a. Get the Followup Email Prompt
    followup_email_prompt = ai_followup_email_prompt(
        client_sdr_id=email_messaging_schedule.client_sdr_id,
        prospect_id=prospect_email.prospect_id,
        override_sequence_id=email_messaging_schedule.email_body_template_id,
    )

    # 3b. Generate the email body
    email_body = generate_email(followup_email_prompt)
    email_body = email_body.get("body")

    # 3c. Create the email body
    reply_email_body = GeneratedMessage(
        prompt=followup_email_prompt,
        completion=email_body,
        message_status=GeneratedMessageStatus.QUEUED_FOR_OUTREACH,
    )
    db.session.add(reply_email_body)
    db.session.commit()

    # 3d. Attach the email body to the email_messaging_schedule
    email_messaging_schedule.body_id = reply_email_body.id

    # 4. Update the email_messaging_schedule
    email_messaging_schedule.send_status = EmailMessagingStatus.SCHEDULED

    # 5. Commit the changes
    db.session.commit()

    return True, "Success"


def collect_and_send_email_messaging_schedule_entries() -> tuple[bool, str]:
    """ Collects and sends email_messaging_schedule entries that need to be sent

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating success and a message
    """
    # Get the first email_messaging_schedule entry that need to be sent
    email_messaging_schedule: EmailMessagingSchedule = EmailMessagingSchedule.query.filter(
        EmailMessagingSchedule.send_status == EmailMessagingStatus.SCHEDULED,
        EmailMessagingSchedule.date_scheduled <= datetime.utcnow(),
    ).first()

    success, message = send_email_messaging_schedule_entry.delay(
        email_messaging_schedule_id=email_messaging_schedule.id,
    )

    return success, message


@celery.task(bind=True, max_retries=3)
def send_email_messaging_schedule_entry(
    email_messaging_schedule_id: int,
) -> tuple[bool, str]:
    """ Sends an email_messaging_schedule entry

    Args:
        email_messaging_schedule_id (int): The ID of the email_messaging_schedule entry to send

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating success and a message
    """
    from src.prospecting.nylas.services import nylas_send_email
    from src.prospecting.services import update_prospect_status_email

    # Get the email_messaging_schedule entry
    email_messaging_schedule: EmailMessagingSchedule = EmailMessagingSchedule.query.get(
        email_messaging_schedule_id)
    if not email_messaging_schedule:
        return False, f"EmailMessage with ID {email_messaging_schedule_id} does not exist"
    if email_messaging_schedule.send_status != EmailMessagingStatus.SCHEDULED:
        return False, f"EmailMessage with ID {email_messaging_schedule_id} is not in SCHEDULED status"

    # Get the past email_messaging_schedule entries (to ensure they are all "SENT")
    past_email_messaging_schedules: list[EmailMessagingSchedule] = EmailMessagingSchedule.query.filter(
        EmailMessagingSchedule.prospect_email_id == email_messaging_schedule.prospect_email_id,
        EmailMessagingSchedule.id < email_messaging_schedule.id,
    ).all()
    for past_email_messaging_schedule in past_email_messaging_schedules:
        if past_email_messaging_schedule.send_status != EmailMessagingStatus.SENT:
            return False, f"Past EmailMessages have not all been SENT"

    # 1. Get the prospect email, generated messages for subject line and body
    prospect_email: ProspectEmail = ProspectEmail.query.get(
        email_messaging_schedule.prospect_email_id)
    subject_line: GeneratedMessage = GeneratedMessage.query.get(
        email_messaging_schedule.subject_line_id)
    body: GeneratedMessage = GeneratedMessage.query.get(
        email_messaging_schedule.body_id)

    # 2. Determine if we are Initial or Followup
    # 2a. Followup emails should use nylas_message_id for reply_to
    reply_to_message_id = None
    if email_messaging_schedule.email_type == EmailMessagingType.FOLLOW_UP_EMAIL:
        # Get the last email_messaging_schedule entry
        last_email_messaging_schedule: EmailMessagingSchedule = EmailMessagingSchedule.query.filter(
            EmailMessagingSchedule.prospect_email_id == email_messaging_schedule.prospect_email_id,
            EmailMessagingSchedule.id < email_messaging_schedule.id,
            EmailMessagingSchedule.nylas_message_id != None,
            EmailMessagingSchedule.send_status == EmailMessagingStatus.SENT,
        ).order_by(EmailMessagingSchedule.id.desc()).first()
        if last_email_messaging_schedule:
            reply_to_message_id = last_email_messaging_schedule.nylas_message_id
        else:
            return False, f"Could not find a previous email to reply to, even though this is a FOLLOW_UP_EMAIL"

    # 3. Send the email
    result: dict = nylas_send_email(
        client_sdr_id=email_messaging_schedule.client_sdr_id,
        prospect_id=prospect_email.prospect_id,
        subject_line=subject_line.completion,
        body=body.completion,
        reply_to_message_id=reply_to_message_id,
        prospect_email_id=prospect_email.id,
    )
    nylas_message_id = result.get("id")
    nylas_thread_id = result.get("thread_id")

    # 4. Update the email_messaging_schedule
    email_messaging_schedule.send_status = EmailMessagingStatus.SENT
    email_messaging_schedule.nylas_message_id = nylas_message_id
    email_messaging_schedule.nylas_thread_id = nylas_thread_id

    # 5. Update the prospect_email
    # 5b. Get the appropriate status
    outreach_status = ProspectEmailOutreachStatus.SENT_OUTREACH if email_messaging_schedule.email_type == EmailMessagingType.INITIAL_EMAIL else ProspectEmailOutreachStatus.BUMPED

    # 5c. Update the prospect_email status
    success, _ = update_prospect_status_email(
        prospect_id=prospect_email.prospect_id,
        new_status=outreach_status,
    )

    # 5d. Update the prospect_email bump count (if applicable)
    if outreach_status == ProspectEmailOutreachStatus.BUMPED:
        prospect_email.times_bumped = prospect_email.times_bumped + 1 if prospect_email.times_bumped else 1

    # 6. Commit the changes
    db.session.commit()

    return True, "Success"

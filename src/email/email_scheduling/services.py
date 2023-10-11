from app import db

from datetime import datetime, timedelta
from typing import Optional
from src.client.models import ClientArchetype
from src.email.email_outbound.models import ProspectEmail
from src.email.email_scheduling.models import EmailMessagingSchedule, EmailMessagingType, EmailMessagingStatus
from src.email.email_sequencing.models import EmailSequenceStep
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
    accepted_followup_email_send_date = initial_email_send_date + timedelta(days=DEFAULT_SENDING_DELAY_INTERVAL)
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
    followup_email_send_date = initial_email_send_date
    while followups_created < FOLLOWUP_LIMIT: # 10 followups max
        # Search for a sequence step that is bumped and has a followup number
        bumped_sequence_step: EmailSequenceStep = EmailSequenceStep.query.filter_by(
            client_sdr_id=client_sdr_id,
            client_archetype_id=prospect.archetype_id,
            bumped_count=followups_created,
        ).first()
        if not bumped_sequence_step:
            break

        followup_email_send_date = followup_email_send_date + timedelta(days=DEFAULT_SENDING_DELAY_INTERVAL)
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

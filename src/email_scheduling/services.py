import random
import pytz
from app import celery, db

from datetime import datetime, timedelta
from sqlalchemy.orm.attributes import flag_modified
from typing import Optional
from src.automation.models import ProcessQueue, ProcessQueueStatus
from src.client.models import ClientArchetype, ClientSDR, SLASchedule
from src.client.sdr.email.models import SDREmailBank, SDREmailSendSchedule
from src.client.sdr.email.services_email_schedule import (
    create_default_sdr_email_send_schedule,
)
from src.email_outbound.models import (
    ProspectEmail,
    ProspectEmailOutreachStatus,
    ProspectEmailStatus,
)
from src.email_scheduling.models import (
    EmailMessagingSchedule,
    EmailMessagingType,
    EmailMessagingStatus,
)
from src.email_sequencing.models import (
    EmailSequenceStep,
    EmailSequenceStepToAssetMapping,
    EmailSubjectLineTemplate,
)
from src.message_generation.models import (
    GeneratedMessage,
    GeneratedMessageEmailType,
    GeneratedMessageStatus,
    GeneratedMessageType,
)
from src.operator_dashboard.models import (
    OperatorDashboardEntry,
    OperatorDashboardEntryPriority,
    OperatorDashboardEntryStatus,
    OperatorDashboardTaskType,
)
from src.operator_dashboard.services import create_operator_dashboard_entry
from src.prospecting.models import Prospect, ProspectInSmartlead, ProspectOverallStatus
from src.smartlead.services import (
    prospect_exists_in_smartlead,
    upload_prospect_to_campaign,
)


FOLLOWUP_LIMIT = 10
DEFAULT_SENDING_DELAY_INTERVAL = 3
DEFAULT_TIMEZONE = "America/Los_Angeles"


def get_email_messaging_schedule_entries(
    client_sdr_id: int,
    prospect_id: Optional[int] = None,
    future_only: Optional[bool] = True,
) -> list[dict]:
    """Gets email_messaging_schedule entries

    Args:
        client_sdr_id (int): ID of the client_sdr
        prospect_id (Optional[int], optional): ID of the prospect. Defaults to None.
        future_only (Optional[bool], optional): Whether to only get future entries. Defaults to True.

    Returns:
        list[dict]: A list of email_messaging_schedule entries
    """
    query = EmailMessagingSchedule.query.filter(
        EmailMessagingSchedule.client_sdr_id == client_sdr_id,
    )

    # Get the prospect email, if prospect_id is provided
    if prospect_id:
        prospect: Prospect = Prospect.query.get(prospect_id)
        prospect_email: ProspectEmail = ProspectEmail.query.get(
            prospect.approved_prospect_email_id
        )
        query = query.filter(
            EmailMessagingSchedule.prospect_email_id == prospect_email.id,
        )

    # Get future entries, if future_only is True
    if future_only:
        query = query.filter(
            EmailMessagingSchedule.date_scheduled >= datetime.utcnow(),
        )

    # Execute the query
    email_messaging_schedules: list[EmailMessagingSchedule] = query.all()

    # Convert to dict
    email_messaging_schedules_dict: list[dict] = []
    email_messaging_schedules_dict = [
        email_messaging_schedule.to_dict()
        for email_messaging_schedule in email_messaging_schedules
    ]

    return email_messaging_schedules_dict


def modify_email_messaging_schedule_entry(
    email_messaging_schedule_id: int,
    date_scheduled: Optional[datetime] = None,
) -> tuple[bool, str]:
    """Modifies an email_messaging_schedule entry's date_scheduled

    Args:
        email_messaging_schedule_id (int): The ID of the email_messaging_schedule entry to modify
        date_scheduled (Optional[datetime], optional): The new date_scheduled. Defaults to None.

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating success and a message
    """
    now = datetime.utcnow()
    utc_timezone = pytz.utc
    now = utc_timezone.localize(now)
    if date_scheduled:
        if date_scheduled.tzinfo is None:
            date_scheduled = utc_timezone.localize(date_scheduled)
        else:
            date_scheduled = date_scheduled.astimezone(utc_timezone)
        if date_scheduled < now:
            return False, "Cannot reschedule an email in the past"

    schedule_entry: EmailMessagingSchedule = EmailMessagingSchedule.query.get(
        email_messaging_schedule_id
    )
    if schedule_entry.send_status == EmailMessagingStatus.SENT:
        return False, "Cannot reschedule a sent email"

    # The email wants to be rescheduled
    if date_scheduled:
        # Get the email before the rescheduled email that has not been sent yet, and track the time
        previous_email: EmailMessagingSchedule = (
            EmailMessagingSchedule.query.filter(
                EmailMessagingSchedule.client_sdr_id == schedule_entry.client_sdr_id,
                EmailMessagingSchedule.prospect_email_id
                == schedule_entry.prospect_email_id,
                EmailMessagingSchedule.date_scheduled < schedule_entry.date_scheduled,
                EmailMessagingSchedule.send_status != EmailMessagingStatus.SENT,
            )
            .order_by(EmailMessagingSchedule.date_scheduled.desc())
            .first()
        )
        boundary_time = previous_email.date_scheduled if previous_email else now
        if boundary_time.tzinfo is None:
            boundary_time = utc_timezone.localize(boundary_time)
        else:
            boundary_time = boundary_time.astimezone(utc_timezone)

        if date_scheduled < boundary_time:
            return (
                False,
                "Cannot reschedule an email to occur before the previous email in the sequence",
            )

        # Get the future emails
        old_date = schedule_entry.date_scheduled
        future_emails: list[
            EmailMessagingSchedule
        ] = EmailMessagingSchedule.query.filter(
            EmailMessagingSchedule.client_sdr_id == schedule_entry.client_sdr_id,
            EmailMessagingSchedule.prospect_email_id
            == schedule_entry.prospect_email_id,
            EmailMessagingSchedule.date_scheduled > old_date,
        ).all()
        if old_date.tzinfo is None:
            old_date = utc_timezone.localize(old_date)
        else:
            old_date = old_date.astimezone(utc_timezone)
        schedule_entry.date_scheduled = date_scheduled
        sequence_step: EmailSequenceStep = EmailSequenceStep.query.get(
            schedule_entry.email_body_template_id
        )

        print(schedule_entry.date_scheduled)

        # Trickle down effect on future emails to preserve cadence
        delay = sequence_step.sequence_delay_days or DEFAULT_SENDING_DELAY_INTERVAL
        date_scheduled = schedule_entry.date_scheduled
        for future_email in future_emails:
            new_date = verify_followup_send_date(
                client_sdr_id=future_email.client_sdr_id,
                followup_send_date=date_scheduled + timedelta(days=delay),
                email_bank_id=None,
            )
            sequence_step: EmailSequenceStep = EmailSequenceStep.query.get(
                future_email.email_body_template_id
            )
            delay = sequence_step.sequence_delay_days or DEFAULT_SENDING_DELAY_INTERVAL
            date_scheduled = new_date
            future_email.date_scheduled = new_date

    db.session.commit()
    return True, "Success"


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
    generate_immediately: Optional[bool] = False,
) -> int:
    """Creates an email_messaging_schedule entry in the database

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
        generate_immediately (Optional[bool], optional): Whether to generate the email immediately. Defaults to False. Degrades performance.

    Returns:
        int: The ID of the created email_messaging_schedule entry
    """
    # As a double check, in case celery goes down or we accidentally doubley create scheduling entries
    # Let's enforce a uniqueness policy that a schedule entry exists iff there is one with the same:
    # - prospect_email_id
    # - email_type
    # - email_body_template_id
    existing_email_messaging_schedule: EmailMessagingSchedule = (
        EmailMessagingSchedule.query.filter(
            EmailMessagingSchedule.prospect_email_id == prospect_email_id,
            EmailMessagingSchedule.email_type == email_type,
            EmailMessagingSchedule.email_body_template_id == email_body_template_id,
        )
        .order_by(EmailMessagingSchedule.id.desc())
        .first()
    )
    if existing_email_messaging_schedule:
        return existing_email_messaging_schedule.id

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

    if generate_immediately:
        if body_id or subject_line_id:
            # If we already have the generated message, don't generate it again
            return email_messaging_schedule.id
        email_messaging_schedule.send_status = EmailMessagingStatus.NEEDS_GENERATION
        db.session.commit()

        tries = 0
        while tries < 3:
            tries += 1
            success, reason = generate_email_messaging_schedule_entry(
                email_messaging_schedule_id=email_messaging_schedule.id
            )
            if not success:
                print(f"Failed to generate email: {reason}")
                if tries == 3:
                    raise Exception(f"Failed to generate email: {reason}")
                continue

            # Temporary measure to prevent sending (this is through SMARTLEAD for the moment)
            email_messaging_schedule.send_status = EmailMessagingStatus.SENT
            db.session.commit()
            break

    return email_messaging_schedule.id


def backfill(date: str):
    # Get the prospects that have a generated message for email body and subject line
    # and where the prospect_email does NOt have schedule entries
    # and the message was created since 03/05/2024

    query = f"""
SELECT
	m.id message_id,
	m.prompt,
	m.completion,
	m.email_type,
	m.message_status,
	p.id prospect_id,
	p.email,
	pe.email_status,
	s.id,
	s.email_type,
	s.email_body_template_id,
	s.email_subject_line_template_id
FROM
	generated_message m
	LEFT JOIN prospect p ON m.prospect_id = p.id
	LEFT JOIN prospect_email pe ON p.approved_prospect_email_id = pe.id
	LEFT JOIN email_messaging_schedule s ON s.prospect_email_id = pe.id
WHERE
	m.message_type = 'EMAIL'
	AND date(m.created_at) = '{date}'
ORDER BY
	email,
	s.email_type,
	m.email_type;
"""
    result = db.session.execute(query).fetchall()
    prospects_missing_schedule = set()
    for row in result:
        message_id = row[0]
        email_type = row[3]
        prospect_id = row[5]
        schedule_id = row[8]
        schedule_email_type = row[9]
        schedule_email_body_template_id = row[10]
        schedule_email_subject_line_template_id = row[11]

        if not schedule_id:
            prospects_missing_schedule.add(prospect_id)

    print(prospects_missing_schedule)
    print(len(prospects_missing_schedule))


@celery.task
def populate_email_messaging_schedule_entries(
    client_sdr_id: int,
    prospect_email_id: int,
    subject_line_id: int,
    body_id: int,
    initial_email_subject_line_template_id: int,
    initial_email_body_template_id: int,
    initial_email_send_date: Optional[datetime] = None,
    generate_immediately: Optional[bool] = False,
) -> list[int]:
    """Populates the email_messaging_schedule table with the appropriate entries

    Will use a helper function to determine the appropriate time to send the email

    Args:
        client_sdr_id (int): ID of the client_sdr
        prospect_email_id (int): ID of the prospect_email
        subject_line_id (int): ID of the subject line (Generated Message)
        body_id (int): ID of the body (Generated Message)
        initial_email_subject_line_template_id (int): ID of the initial email subject line template (EmailSubjectLine)
        initial_email_body_template_id (int): ID of the initial email body template (EmailSequenceStep)
        DEPRECATED - initial_email_send_date (Optional[datetime], optional): Time to send first email. Defaults to None.
        generate_immediately (Optional[bool], optional): Whether to generate the email immediately. Defaults to False. Degrades performance.

    Returns:
        list[int]: A list of the email_messaging_schedule IDs
    """
    # Get the Archetype ID from the prospect
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    prospect: Prospect = Prospect.query.get(prospect_email.prospect_id)

    # LOGGER (delete me eventually): If generate immediately, then we know it is a Smartlead campaign (for now), and we should try to get the ProspectInSmartlead model and update the log
    log = None
    if generate_immediately:
        log: ProspectInSmartlead = ProspectInSmartlead.query.filter(
            ProspectInSmartlead.prospect_id == prospect.id
        ).first()
        if log:
            log.log.append(
                f"populate_email_messaging_schedule_entries ({datetime.utcnow()}): Starting to populate"
            )
            flag_modified(log, "log")
            db.session.commit()

    # Track all the scheduled email ids
    email_ids = []

    # Make sure we don't have any existing email_messaging_schedule entries
    existing_email_messaging_schedules: list[
        EmailMessagingSchedule
    ] = EmailMessagingSchedule.query.filter(
        EmailMessagingSchedule.prospect_email_id == prospect_email_id,
    ).all()
    if existing_email_messaging_schedules:
        if log:  # LOGGER (delete me eventually)
            log.log.append(
                f"populate_email_messaging_schedule_entries ({datetime.utcnow()}): Found existing email messaging schedule entries. Going into the edge case checker."
            )
            flag_modified(log, "log")
            db.session.commit()
        # If we have existing email_messaging_schedule entries, let's check for an edge case:
        # We have a ProspectEmail but the email_status is not yet SENT. We also have a ProcessQueue item for this email that is FAILED.
        # We also don't see this email in Smartlead. This means that the email was not sent and we should not send it again.
        prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
        if prospect_email and prospect_email.email_status != ProspectEmailStatus.SENT:
            pq_entry: ProcessQueue = ProcessQueue.query.filter(
                ProcessQueue.type == "populate_email_messaging_schedule_entries",
                ProcessQueue.meta_data.contains(
                    {"args": {"prospect_email_id": prospect_email_id}}
                ),
            ).first()
            if pq_entry and not prospect_exists_in_smartlead(prospect.id):
                upload_prospect_to_campaign.delay(prospect.id)
                return [
                    True,
                    [email.id for email in existing_email_messaging_schedules],
                ]

        return [False, [email.id for email in existing_email_messaging_schedules]]

    # Get the next available send date
    initial_email_send_date = get_initial_email_send_date(
        client_sdr_id=client_sdr_id,
        email_bank_id=None,
    )

    # Create the initial email entry
    initial_email_id = create_email_messaging_schedule_entry(
        client_sdr_id=client_sdr_id,
        prospect_email_id=prospect_email_id,
        email_type=EmailMessagingType.INITIAL_EMAIL,
        email_subject_line_template_id=initial_email_subject_line_template_id,
        email_body_template_id=initial_email_body_template_id,
        send_status=(
            EmailMessagingStatus.SCHEDULED
            if not generate_immediately  # Temporary measure to prevent sending (this is through SMARTLEAD for the moment)
            else EmailMessagingStatus.SENT
        ),
        date_scheduled=initial_email_send_date,
        subject_line_id=subject_line_id,
        body_id=body_id,
    )
    email_ids.append(initial_email_id)
    initial_email_template: EmailSequenceStep = EmailSequenceStep.query.get(
        initial_email_body_template_id
    )

    # Find the ACCEPTED sequence step
    # Intelligently choose one. Find the assets used by previous steps
    mappings: list[
        EmailSequenceStepToAssetMapping
    ] = EmailSequenceStepToAssetMapping.query.filter_by(
        email_sequence_step_id=initial_email_body_template_id
    ).all()
    used_asset_ids = [mapping.client_assets_id for mapping in mappings]

    accepted_sequence_steps: list[
        EmailSequenceStep
    ] = EmailSequenceStep.query.filter_by(
        client_sdr_id=client_sdr_id,
        client_archetype_id=prospect.archetype_id,
        overall_status=ProspectOverallStatus.ACCEPTED,
        active=True,
        # default=True,
    ).all()
    if not accepted_sequence_steps:
        return [True, email_ids]

    accepted_sequence_step: EmailSequenceStep = random.choice(accepted_sequence_steps)
    # Find the ACCEPTED sequence step that does NOT use the same assets. Otherwise default to a random one
    for sequence_step in accepted_sequence_steps:
        mappings: list[
            EmailSequenceStepToAssetMapping
        ] = EmailSequenceStepToAssetMapping.query.filter_by(
            email_sequence_step_id=sequence_step.id
        ).all()
        new_asset_ids = [mapping.client_assets_id for mapping in mappings]
        if not any(asset_id in used_asset_ids for asset_id in new_asset_ids):
            accepted_sequence_step = sequence_step
            used_asset_ids.extend(new_asset_ids)
            break
    if not accepted_sequence_step:
        return [True, email_ids]

    # Create the accepted (1 time) followup
    delay_days = (
        initial_email_template.sequence_delay_days or DEFAULT_SENDING_DELAY_INTERVAL
    )
    random_minute_offset = random.randint(-15, 15)
    accepted_followup_email_send_date = initial_email_send_date + timedelta(
        days=delay_days, minutes=random_minute_offset
    )
    accepted_followup_email_send_date = verify_followup_send_date(
        client_sdr_id=client_sdr_id,
        followup_send_date=accepted_followup_email_send_date,
        email_bank_id=None,
    )
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
        generate_immediately=generate_immediately,
    )
    email_ids.append(accepted_followup_email_id)

    # Create the followups
    followups_created = 1
    followup_email_send_date = accepted_followup_email_send_date
    delay_days = (
        accepted_sequence_step.sequence_delay_days or DEFAULT_SENDING_DELAY_INTERVAL
    )
    while followups_created < FOLLOWUP_LIMIT:  # 10 followups max
        # Search for a sequence step that is bumped and has a followup number
        bumped_sequence_steps: list[
            EmailSequenceStep
        ] = EmailSequenceStep.query.filter_by(
            client_sdr_id=client_sdr_id,
            client_archetype_id=prospect.archetype_id,
            bumped_count=followups_created,
            active=True,
            # default=True,
        ).all()
        if not bumped_sequence_steps:
            break

        bumped_sequence_step = random.choice(bumped_sequence_steps)

        # Find the BUMPED sequence step that does NOT use the same assets. Otherwise default to a random one
        for sequence_step in bumped_sequence_steps:
            mappings: list[
                EmailSequenceStepToAssetMapping
            ] = EmailSequenceStepToAssetMapping.query.filter_by(
                email_sequence_step_id=sequence_step.id
            ).all()
            new_asset_ids = [mapping.client_assets_id for mapping in mappings]
            if not any(asset_id in used_asset_ids for asset_id in new_asset_ids):
                bumped_sequence_step = sequence_step
                used_asset_ids.extend(new_asset_ids)
                break

        if not bumped_sequence_step:
            break

        random_minute_offset = random.randint(-15, 15)
        followup_email_send_date = followup_email_send_date + timedelta(
            days=delay_days, minutes=random_minute_offset
        )
        followup_email_send_date = verify_followup_send_date(
            client_sdr_id=client_sdr_id,
            followup_send_date=followup_email_send_date,
            email_bank_id=None,
        )
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
            generate_immediately=generate_immediately,
        )
        email_ids.append(followup_email_id)
        followups_created += 1
        delay_days = (
            bumped_sequence_step.sequence_delay_days or DEFAULT_SENDING_DELAY_INTERVAL
        )

    # LOGGER (delete me eventually)
    if log:
        log.log.append(
            f"populate_email_messaging_schedule_entries ({datetime.utcnow()}): Finished populating email schedules"
        )
        flag_modified(log, "log")
        db.session.commit()

    # SMARTLEAD: If we have generated immediately, this implies that we should send the prospect to Smartlead to upload
    if generate_immediately:
        # LOGGER (delete me eventually)
        if log:
            log.log.append(
                f"populate_email_messaging_schedule_entries ({datetime.utcnow()}): Sending to Smartlead"
            )
            flag_modified(log, "log")
            db.session.commit()
        upload_prospect_to_campaign.delay(prospect.id)

    return [True, email_ids]


def get_initial_email_send_date(
    client_sdr_id: int, email_bank_id: Optional[int] = None
) -> datetime:
    """Gets the next available send date for an email

    Args:
        client_sdr_id (int): ID of the client_sdr
        email_bank_id (Optional[int], optional): ID of the email_bank. Defaults to None.

    Raises:
        Exception: If the sending schedule is not set up correctly

    Returns:
        datetime: The next available send date
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    if not email_bank_id:
        # Get the email bank (random for now)
        email_bank: SDREmailBank = SDREmailBank.query.filter(
            SDREmailBank.client_sdr_id == client_sdr_id,
            # SDREmailBank.nylas_account_id != None, #TODO: Restructure to not use nylas
            # SDREmailBank.nylas_auth_code != None,
            # SDREmailBank.nylas_active == True,
        ).first()
    else:
        email_bank: SDREmailBank = SDREmailBank.query.get(email_bank_id)

    # Get this SDRs sending schedule
    sending_schedule: SDREmailSendSchedule = SDREmailSendSchedule.query.filter_by(
        client_sdr_id=client_sdr_id,
        email_bank_id=email_bank.id,
    ).first()
    if not sending_schedule:
        send_schedule_id = create_default_sdr_email_send_schedule(
            client_sdr_id=client_sdr_id,
            email_bank_id=email_bank.id,
        )
        sending_schedule = SDREmailSendSchedule.query.get(send_schedule_id)
    if sending_schedule.days == [] or sending_schedule.days is None:
        raise Exception(
            "This inbox's sending schedule is not set up correctly. No sending days are set."
        )

    # Get the next available date
    furthest_initial_email: EmailMessagingSchedule = (
        EmailMessagingSchedule.query.filter(
            EmailMessagingSchedule.client_sdr_id == client_sdr_id,
            EmailMessagingSchedule.email_type == EmailMessagingType.INITIAL_EMAIL,
            EmailMessagingSchedule.send_status == EmailMessagingStatus.NEEDS_GENERATION
            or EmailMessagingSchedule.send_status == EmailMessagingStatus.SCHEDULED,
        )
        .order_by(EmailMessagingSchedule.date_scheduled.desc())
        .first()
    )
    if not furthest_initial_email:
        # If no initial emails have been sent, choose tomorrow
        send_date = datetime.utcnow() + timedelta(days=1)
    else:
        send_date = furthest_initial_email.date_scheduled

        # Get the send cadence according to the SDR's Email SLA (Warming Schedule)
        sla_schedule: SLASchedule = SLASchedule.query.filter(
            SLASchedule.client_sdr_id == client_sdr_id,
            SLASchedule.start_date <= send_date,
            SLASchedule.end_date + timedelta(days=3)
            >= send_date,  # Give a little buffer
        ).first()
        email_sla = sla_schedule.email_volume if sla_schedule else 5
        email_sla = email_sla or 5
        try:
            minute_cadence = 60 / (
                email_sla
                / len(sending_schedule.days)
                / (sending_schedule.end_time.hour - sending_schedule.start_time.hour)
            )
        except:
            minute_cadence = 60

        send_date = send_date + timedelta(minutes=minute_cadence)

    # Convert the send_date to the Inbox timezone
    utc_tz = pytz.timezone("UTC")
    inbox_tz = pytz.timezone(
        sending_schedule.time_zone or client_sdr.timezone or DEFAULT_TIMEZONE
    )
    localized = utc_tz.localize(send_date)
    send_date = localized.astimezone(inbox_tz)

    # Verify that the time is within the sending schedule, otherwise adjust
    if send_date.time() < sending_schedule.start_time:
        # If the time is before the start time, bump up to the start time
        send_date = send_date.replace(
            hour=sending_schedule.start_time.hour,
            minute=sending_schedule.start_time.minute,
            second=0,
            microsecond=0,
        )
    elif send_date.time() > sending_schedule.end_time:
        # If the time is after the end time, bump up to the next day's start time
        send_date = send_date.replace(
            hour=sending_schedule.start_time.hour,
            minute=sending_schedule.start_time.minute,
            second=0,
            microsecond=0,
        )
        send_date = send_date + timedelta(days=1)

    # Verify that the date is within the sending schedule, otherwise adjust
    while send_date.weekday() not in sending_schedule.days:
        send_date = send_date + timedelta(days=1)

    # Get the send cadence according to the SDR's Email SLA (Warming Schedule)
    sla_schedule: SLASchedule = SLASchedule.query.filter(
        SLASchedule.client_sdr_id == client_sdr_id,
        SLASchedule.start_date <= send_date,
        SLASchedule.end_date + timedelta(days=3) >= send_date,  # Give a little buffer
    ).first()
    email_sla = sla_schedule.email_volume if sla_schedule else 5
    email_sla = email_sla or 5
    try:
        minute_cadence = 60 / (
            email_sla
            / len(sending_schedule.days)
            / (sending_schedule.end_time.hour - sending_schedule.start_time.hour)
        )
    except:
        minute_cadence = 60

    # Convert the send_date back to UTC
    utc_send_date = send_date.astimezone(utc_tz)

    return utc_send_date


def verify_followup_send_date(
    client_sdr_id: int,
    followup_send_date: datetime,
    email_bank_id: Optional[int] = None,
) -> datetime:
    """Verifies that the followup_send_date is valid

    Args:
        client_sdr_id (int): ID of the client_sdr
        followup_send_date (datetime): The date the email is scheduled to be sent
        email_bank_id (Optional[int], optional): ID of the email_bank. Defaults to None.

    Raises:
        Exception: If the sending schedule is not set up correctly

    Returns:
        datetime: The next available send date
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    if not email_bank_id:
        # Get the email bank (random for now)
        email_bank: SDREmailBank = SDREmailBank.query.filter(
            SDREmailBank.client_sdr_id == client_sdr_id,
            # SDREmailBank.nylas_account_id != None, #TODO: Restructure to not use nylas
            # SDREmailBank.nylas_auth_code != None,
            # SDREmailBank.nylas_active == True,
        ).first()
    else:
        email_bank: SDREmailBank = SDREmailBank.query.get(email_bank_id)

    # Get this SDRs sending schedule
    sending_schedule: SDREmailSendSchedule = SDREmailSendSchedule.query.filter_by(
        client_sdr_id=client_sdr_id,
        email_bank_id=email_bank.id,
    ).first()
    if not sending_schedule:
        send_schedule_id = create_default_sdr_email_send_schedule(
            client_sdr_id=client_sdr_id,
            email_bank_id=email_bank.id,
        )
        sending_schedule = SDREmailSendSchedule.query.get(send_schedule_id)
    if sending_schedule.days == [] or sending_schedule.days is None:
        raise Exception(
            "This inbox's sending schedule is not set up correctly. No sending days are set."
        )

    # Convert the send_date to the Inbox timezone
    utc_tz = pytz.timezone("UTC")
    inbox_tz = pytz.timezone(
        sending_schedule.time_zone or client_sdr.timezone or DEFAULT_TIMEZONE
    )
    try:
        localized = utc_tz.localize(followup_send_date)
    except:
        localized = followup_send_date
    followup_send_date = localized.astimezone(inbox_tz)

    # Verify that the date is within the sending schedule, otherwise adjust
    while followup_send_date.weekday() not in sending_schedule.days:
        followup_send_date = followup_send_date + timedelta(days=1)

    return followup_send_date


@celery.task(bind=True, max_retries=3)
def collect_and_generate_email_messaging_schedule_entries(self) -> tuple[bool, str]:
    """Collects and generates email_messaging_schedule entries that need to be generated

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating success and a message
    """
    # TODO: Increase limit
    # Get the first email_messaging_schedule entry that need to be generated
    email_messaging_schedule: EmailMessagingSchedule = (
        EmailMessagingSchedule.query.filter(
            EmailMessagingSchedule.send_status == EmailMessagingStatus.NEEDS_GENERATION,
            EmailMessagingSchedule.date_scheduled
            <= datetime.utcnow() + timedelta(days=1),
        ).first()
    )

    if not email_messaging_schedule:
        return True, "No email_messaging_schedule entries to generate"

    generate_email_messaging_schedule_entry.apply_async(
        kwargs={
            "email_messaging_schedule_id": email_messaging_schedule.id,
        },
        queue="email_scheduler",
        routing_key="email_scheduler",
        prioriy=2,
    )

    return True, "Registered task"


@celery.task(bind=True, max_retries=3)
def generate_email_messaging_schedule_entry(
    self,
    email_messaging_schedule_id: int,
) -> tuple[bool, str]:
    """Generates an email_messaging_schedule entry

    Args:
        email_messaging_schedule_id (int): The ID of the email_messaging_schedule entry to generate

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating success and a message
    """
    from src.message_generation.email.services import (
        ai_followup_email_prompt,
        generate_email,
    )

    # Get the email_messaging_schedule entry
    email_messaging_schedule: EmailMessagingSchedule = EmailMessagingSchedule.query.get(
        email_messaging_schedule_id
    )
    if not email_messaging_schedule:
        return (
            False,
            f"EmailMessagingSchedule with ID {email_messaging_schedule_id} does not exist",
        )
    if email_messaging_schedule.send_status != EmailMessagingStatus.NEEDS_GENERATION:
        return (
            False,
            f"EmailMessagingSchedule with ID {email_messaging_schedule_id} is not in NEEDS_GENERATION status",
        )

    # Generate the email
    # 1. Get the prospect email
    prospect_email: ProspectEmail = ProspectEmail.query.get(
        email_messaging_schedule.prospect_email_id
    )

    # 2. Create the subject line
    # 2a. Get the subject line from the latest send
    last_messaging_schedule: EmailMessagingSchedule = (
        EmailMessagingSchedule.query.filter(
            EmailMessagingSchedule.prospect_email_id == prospect_email.id,
            EmailMessagingSchedule.subject_line_id != None,
        )
        .order_by(EmailMessagingSchedule.id.desc())
        .first()
    )
    if not last_messaging_schedule:
        # Delete entry
        db.session.delete(email_messaging_schedule)
        db.session.commit()
        return (
            False,
            f"EmailMessagingSchedule with ID {email_messaging_schedule_id} does not have a subject line to reply to",
        )
    subject_line: GeneratedMessage = GeneratedMessage.query.get(
        last_messaging_schedule.subject_line_id
    )
    subject_line_text: str = subject_line.completion

    # 2b. Create the subject line
    reply_subject_line_text = f"Re: {subject_line_text}"
    reply_subject_line: GeneratedMessage = GeneratedMessage(
        prompt="Hardcoded: Reply Subject Line",
        completion=reply_subject_line_text,
        prospect_id=prospect_email.prospect_id,
        message_status=GeneratedMessageStatus.QUEUED_FOR_OUTREACH,
        message_type=GeneratedMessageType.EMAIL,
        email_type=GeneratedMessageEmailType.SUBJECT_LINE,
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
        prospect_id=prospect_email.prospect_id,
        message_status=GeneratedMessageStatus.QUEUED_FOR_OUTREACH,
        message_type=GeneratedMessageType.EMAIL,
        email_type=GeneratedMessageEmailType.BODY,
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


@celery.task(bind=True, max_retries=3)
def collect_and_send_email_messaging_schedule_entries(self) -> tuple[bool, str]:
    """Collects and sends email_messaging_schedule entries that need to be sent

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating success and a message
    """
    # Get the first email_messaging_schedule entry that need to be sent
    email_messaging_schedule: EmailMessagingSchedule = (
        EmailMessagingSchedule.query.filter(
            EmailMessagingSchedule.send_status == EmailMessagingStatus.SCHEDULED,
            EmailMessagingSchedule.date_scheduled <= datetime.utcnow(),
        ).first()
    )

    if not email_messaging_schedule:
        return True, "No email_messaging_schedule entries to send"

    send_email_messaging_schedule_entry.apply_async(
        kwargs={
            "email_messaging_schedule_id": email_messaging_schedule.id,
        },
        queue="email_scheduler",
        routing_key="email_scheduler",
        prioriy=1,
    )

    return True, "Registered task"


@celery.task(bind=True, max_retries=3)
def send_email_messaging_schedule_entry(
    self,
    email_messaging_schedule_id: int,
) -> tuple[bool, str]:
    """Sends an email_messaging_schedule entry

    Args:
        email_messaging_schedule_id (int): The ID of the email_messaging_schedule entry to send

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating success and a message
    """
    from src.prospecting.nylas.services import nylas_send_email
    from src.prospecting.services import update_prospect_status_email

    # Get the email_messaging_schedule entry
    email_messaging_schedule: EmailMessagingSchedule = EmailMessagingSchedule.query.get(
        email_messaging_schedule_id
    )
    if not email_messaging_schedule:
        return (
            False,
            f"EmailMessage with ID {email_messaging_schedule_id} does not exist",
        )
    if email_messaging_schedule.send_status != EmailMessagingStatus.SCHEDULED:
        return (
            False,
            f"EmailMessage with ID {email_messaging_schedule_id} is not in SCHEDULED status",
        )

    # Get the past email_messaging_schedule entries (to ensure they are all "SENT")
    past_email_messaging_schedules: list[
        EmailMessagingSchedule
    ] = EmailMessagingSchedule.query.filter(
        EmailMessagingSchedule.prospect_email_id
        == email_messaging_schedule.prospect_email_id,
        EmailMessagingSchedule.id < email_messaging_schedule.id,
    ).all()
    for past_email_messaging_schedule in past_email_messaging_schedules:
        if past_email_messaging_schedule.send_status != EmailMessagingStatus.SENT:
            return False, f"Past EmailMessages have not all been SENT"

    # 1. Get the prospect email, generated messages for subject line and body
    prospect_email: ProspectEmail = ProspectEmail.query.get(
        email_messaging_schedule.prospect_email_id
    )
    subject_line: GeneratedMessage = GeneratedMessage.query.get(
        email_messaging_schedule.subject_line_id
    )
    body: GeneratedMessage = GeneratedMessage.query.get(
        email_messaging_schedule.body_id
    )

    # 2. Determine if we are Initial or Followup
    # 2a. Followup emails should use nylas_message_id for reply_to
    reply_to_message_id = None
    if email_messaging_schedule.email_type == EmailMessagingType.FOLLOW_UP_EMAIL:
        # Get the last email_messaging_schedule entry
        last_email_messaging_schedule: EmailMessagingSchedule = (
            EmailMessagingSchedule.query.filter(
                EmailMessagingSchedule.prospect_email_id
                == email_messaging_schedule.prospect_email_id,
                EmailMessagingSchedule.id < email_messaging_schedule.id,
                EmailMessagingSchedule.nylas_message_id != None,
                EmailMessagingSchedule.send_status == EmailMessagingStatus.SENT,
            )
            .order_by(EmailMessagingSchedule.id.desc())
            .first()
        )
        if last_email_messaging_schedule:
            reply_to_message_id = last_email_messaging_schedule.nylas_message_id
        else:
            return (
                False,
                f"Could not find a previous email to reply to, even though this is a FOLLOW_UP_EMAIL",
            )

        # 2aa. If the prospect email record is not SENT_OUTREACH or EMAIL_OPENED, we should not send and delete the message
        if (
            prospect_email.outreach_status != ProspectEmailOutreachStatus.SENT_OUTREACH
            and prospect_email.outreach_status
            != ProspectEmailOutreachStatus.EMAIL_OPENED
        ):
            # Delete the messages
            db.session.delete(email_messaging_schedule)
            db.session.commit()
            return (
                False,
                f"ProspectEmail with ID {prospect_email.id} is not in SENT_OUTREACH or EMAIL_OPENED status",
            )

    # 3. Send the email
    result: dict = nylas_send_email(
        client_sdr_id=email_messaging_schedule.client_sdr_id,
        prospect_id=prospect_email.prospect_id,
        subject=subject_line.completion,
        body=body.completion,
        reply_to_message_id=reply_to_message_id,
        prospect_email_id=prospect_email.id,
    )
    nylas_message_id = result.get("id")
    nylas_thread_id = result.get("thread_id")
    time_since_epoch = result.get("date")
    if not time_since_epoch:
        return False, "Failed to send email"
    utc_datetime = datetime.utcfromtimestamp(time_since_epoch)

    # 3b. Update future send dates
    future_email_messaging_schedules: list[EmailMessagingSchedule] = (
        EmailMessagingSchedule.query.filter(
            EmailMessagingSchedule.prospect_email_id
            == email_messaging_schedule.prospect_email_id,
            EmailMessagingSchedule.id > email_messaging_schedule.id,
        )
        .order_by(EmailMessagingSchedule.id.asc())
        .all()
    )
    step: EmailSequenceStep = EmailSequenceStep.query.get(
        email_messaging_schedule.email_body_template_id
    )
    delay = step.sequence_delay_days or DEFAULT_SENDING_DELAY_INTERVAL
    new_time = utc_datetime + timedelta(days=delay)
    new_time = verify_followup_send_date(
        client_sdr_id=email_messaging_schedule.client_sdr_id,
        followup_send_date=new_time,
        email_bank_id=None,
    )
    for future_email_messaging_schedule in future_email_messaging_schedules:
        future_email_messaging_schedule.date_scheduled = new_time

        step: EmailSequenceStep = EmailSequenceStep.query.get(
            future_email_messaging_schedule.email_body_template_id
        )
        random_minute_offset = random.randint(-15, 15)
        new_time = new_time + timedelta(
            days=step.sequence_delay_days or DEFAULT_SENDING_DELAY_INTERVAL,
            minutes=random_minute_offset,
        )
        new_time = verify_followup_send_date(
            client_sdr_id=email_messaging_schedule.client_sdr_id,
            followup_send_date=new_time,
            email_bank_id=None,
        )

    # 4. Update the email_messaging_schedule
    email_messaging_schedule.send_status = EmailMessagingStatus.SENT
    email_messaging_schedule.nylas_message_id = nylas_message_id
    email_messaging_schedule.nylas_thread_id = nylas_thread_id

    # 4b. Update the generated_message
    now = datetime.utcnow()
    subject_line.message_status = GeneratedMessageStatus.SENT
    subject_line.date_sent = now
    body.message_status = GeneratedMessageStatus.SENT
    body.date_sent = now

    # 4c. Get the templates from the generated message and increment use count
    subject_line_template: EmailSubjectLineTemplate = (
        EmailSubjectLineTemplate.query.get(subject_line.email_subject_line_template_id)
    )
    # if subject_line_template:
    #     subject_line_template.times_used = (
    #         subject_line_template.times_used + 1
    #         if subject_line_template.times_used
    #         else 1
    #     )
    body_template: EmailSequenceStep = EmailSequenceStep.query.get(
        body.email_sequence_step_template_id
    )
    # if body_template:
    #     body_template.times_used = (
    #         body_template.times_used + 1 if body_template.times_used else 1
    #     )

    # 5. Update the prospect_email
    # 5b. Get the appropriate status
    outreach_status = (
        ProspectEmailOutreachStatus.SENT_OUTREACH
        if email_messaging_schedule.email_type == EmailMessagingType.INITIAL_EMAIL
        else ProspectEmailOutreachStatus.BUMPED
    )
    prospect_email.email_status = ProspectEmailStatus.SENT

    # 5c. Update the prospect_email status
    success, _ = update_prospect_status_email(
        prospect_id=prospect_email.prospect_id,
        new_status=outreach_status,
    )

    # 5d. Update the prospect_email bump count (if applicable)
    if outreach_status == ProspectEmailOutreachStatus.BUMPED:
        prospect_email.times_bumped = (
            prospect_email.times_bumped + 1 if prospect_email.times_bumped else 1
        )

    # 6. Commit the changes
    db.session.commit()

    return True, "Success"


def create_calendar_link_needed_operator_dashboard_card(client_sdr_id: int):
    create_operator_dashboard_entry(
        client_sdr_id=client_sdr_id,
        urgency=OperatorDashboardEntryPriority.MEDIUM,
        tag="connect_calendar_{client_sdr_id}".format(client_sdr_id=client_sdr_id),
        emoji="🗓",
        title="Connect Calendar",
        subtitle="In order to schedule contacts effectively, you will need to link your calendar to SellScale (i.e. Calendly, Hubspot, etc)",
        cta="Connect Calendar",
        cta_url="/",
        status=OperatorDashboardEntryStatus.PENDING,
        due_date=datetime.now() + timedelta(days=1),
        task_type=OperatorDashboardTaskType.ADD_CALENDAR_LINK,
        task_data={
            "client_sdr_id": client_sdr_id,
        },
    )

    return True

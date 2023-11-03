from datetime import datetime, timedelta
from freezegun import freeze_time

import mock
import pytz
from app import db, app
from src.email_scheduling.models import EmailMessagingSchedule, EmailMessagingStatus, EmailMessagingType
from src.email_scheduling.services import DEFAULT_SENDING_DELAY_INTERVAL, create_email_messaging_schedule_entry, generate_email_messaging_schedule_entry, get_initial_email_send_date, modify_email_messaging_schedule_entry, populate_email_messaging_schedule_entries, verify_followup_send_date
from src.message_generation.models import GeneratedMessage
from src.prospecting.models import ProspectOverallStatus
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_prospect,
    basic_prospect_email,
    basic_archetype,
    basic_email_sequence_step,
    basic_email_subject_line_template,
    basic_generated_message,
    basic_sdr_email_bank,
    basic_sdr_email_send_schedule
)
from tests.test_utils.decorators import use_app_context


@use_app_context
def test_modify_email_messaging_schedule_entry():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype)
    prospect_email = basic_prospect_email(prospect)
    email_body_template = basic_email_sequence_step(
        client_sdr=client_sdr,
        client_archetype=archetype,
        sequence_delay_days=3 # Monday send, Thursday next
    )
    email_subject_line_template = basic_email_subject_line_template(
        client_sdr, archetype)
    subject_line = basic_generated_message(prospect)
    body = basic_generated_message(prospect)
    email_bank = basic_sdr_email_bank(client_sdr)
    schedule = basic_sdr_email_send_schedule(client_sdr, email_bank)

    bump_accepted = basic_email_sequence_step(
        client_sdr=client_sdr,
        client_archetype=archetype,
        overall_status=ProspectOverallStatus.ACCEPTED,
        default=True,
        sequence_delay_days=1 # Thursday send, Friday next
    )
    bump_1 = basic_email_sequence_step(
        client_sdr=client_sdr,
        client_archetype=archetype,
        overall_status=ProspectOverallStatus.BUMPED,
        bumped_count=1,
        default=True,
        sequence_delay_days=1 # Friday send, Monday next
    )
    bump_2 = basic_email_sequence_step(
        client_sdr=client_sdr,
        client_archetype=archetype,
        overall_status=ProspectOverallStatus.BUMPED,
        bumped_count=2,
        default=True,
    )

    pst = pytz.timezone('America/Los_Angeles')
    current_date = datetime.now(pst)
    last_sunday = current_date.replace(year=2023, month=10, day=15, hour=9, minute=0, second=0, microsecond=0) # Last Sunday because we offset by 1 day
    this_monday = current_date.replace(year=2023, month=10, day=16, hour=9, minute=0, second=0, microsecond=0)
    this_thursday = current_date.replace(year=2023, month=10, day=19, hour=9, minute=0, second=0, microsecond=0)
    this_friday = current_date.replace(year=2023, month=10, day=20, hour=9, minute=0, second=0, microsecond=0)
    next_monday = current_date.replace(year=2023, month=10, day=23, hour=9, minute=0, second=0, microsecond=0)

    this_wednesday = current_date.replace(year=2023, month=10, day=18, hour=9, minute=0, second=0, microsecond=0)

    with freeze_time(last_sunday):
        assert EmailMessagingSchedule.query.count() == 0
        ids = populate_email_messaging_schedule_entries(
            client_sdr_id=client_sdr.id,
            prospect_email_id=prospect_email.id,
            subject_line_id=subject_line.id,
            body_id=body.id,
            initial_email_subject_line_template_id=email_subject_line_template.id,
            initial_email_body_template_id=email_body_template.id,
        )
        assert EmailMessagingSchedule.query.count() == 4
        assert len(ids) == 4
        assert EmailMessagingSchedule.query.get(ids[0]).email_type == EmailMessagingType.INITIAL_EMAIL
        assert EmailMessagingSchedule.query.get(ids[0]).date_scheduled.date() == this_monday.date()
        assert EmailMessagingSchedule.query.get(ids[1]).email_type == EmailMessagingType.FOLLOW_UP_EMAIL
        assert EmailMessagingSchedule.query.get(ids[1]).date_scheduled.date() == this_thursday.date()
        assert EmailMessagingSchedule.query.get(ids[2]).email_type == EmailMessagingType.FOLLOW_UP_EMAIL
        assert EmailMessagingSchedule.query.get(ids[2]).date_scheduled.date() == this_friday.date()
        assert EmailMessagingSchedule.query.get(ids[3]).email_type == EmailMessagingType.FOLLOW_UP_EMAIL
        assert EmailMessagingSchedule.query.get(ids[3]).date_scheduled.date() == next_monday.date()

        success, _ = modify_email_messaging_schedule_entry(
            email_messaging_schedule_id=ids[1],
            date_scheduled=this_wednesday
        )
        assert success
        assert EmailMessagingSchedule.query.get(ids[1]).date_scheduled.date() == this_wednesday.date()
        assert EmailMessagingSchedule.query.get(ids[2]).date_scheduled.date() == this_thursday.date()
        assert EmailMessagingSchedule.query.get(ids[3]).date_scheduled.date() == this_friday.date()

        success, reason = modify_email_messaging_schedule_entry(
            email_messaging_schedule_id=ids[1],
            date_scheduled=last_sunday - timedelta(days=1)
        )
        assert not success
        assert reason == "Cannot reschedule an email in the past"

        success, reason = modify_email_messaging_schedule_entry(
            email_messaging_schedule_id=ids[1],
            date_scheduled=this_monday - timedelta(days=1)
        )
        assert not success
        assert reason == "Cannot reschedule an email to occur before the previous email in the sequence"


@use_app_context
def test_create_email_messaging_schedule_entry():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype)
    prospect_email = basic_prospect_email(prospect)
    email_body_template = basic_email_sequence_step(client_sdr, archetype)
    email_subject_line_template = basic_email_subject_line_template(
        client_sdr, archetype)
    subject_line = basic_generated_message(prospect)
    body = basic_generated_message(prospect)

    assert EmailMessagingSchedule.query.count() == 0
    id = create_email_messaging_schedule_entry(
        client_sdr_id=client_sdr.id,
        prospect_email_id=prospect_email.id,
        email_type=EmailMessagingType.INITIAL_EMAIL,
        email_body_template_id=email_body_template.id,
        send_status=EmailMessagingStatus.SCHEDULED,
        date_scheduled=datetime.utcnow(),
        email_subject_line_template_id=email_subject_line_template.id,
        subject_line_id=subject_line.id,
        body_id=body.id
    )
    assert EmailMessagingSchedule.query.count() == 1
    schedule: EmailMessagingSchedule = EmailMessagingSchedule.query.get(id)
    assert schedule.client_sdr_id == client_sdr.id
    assert schedule.prospect_email_id == prospect_email.id
    assert schedule.email_type == EmailMessagingType.INITIAL_EMAIL
    assert schedule.email_body_template_id == email_body_template.id
    assert schedule.send_status == EmailMessagingStatus.SCHEDULED
    assert schedule.email_subject_line_template_id == email_subject_line_template.id
    assert schedule.subject_line_id == subject_line.id
    assert schedule.body_id == body.id


@use_app_context
def test_populate_email_messaging_schedule_entries():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype)
    prospect_email = basic_prospect_email(prospect)
    email_body_template = basic_email_sequence_step(
        client_sdr=client_sdr,
        client_archetype=archetype,
        sequence_delay_days=3 # Monday send, Thursday next
    )
    email_subject_line_template = basic_email_subject_line_template(
        client_sdr, archetype)
    subject_line = basic_generated_message(prospect)
    body = basic_generated_message(prospect)
    email_bank = basic_sdr_email_bank(client_sdr)
    schedule = basic_sdr_email_send_schedule(client_sdr, email_bank)

    bump_accepted = basic_email_sequence_step(
        client_sdr=client_sdr,
        client_archetype=archetype,
        overall_status=ProspectOverallStatus.ACCEPTED,
        default=True,
        sequence_delay_days=1 # Thursday send, Friday next
    )
    bump_1 = basic_email_sequence_step(
        client_sdr=client_sdr,
        client_archetype=archetype,
        overall_status=ProspectOverallStatus.BUMPED,
        bumped_count=1,
        default=True,
        sequence_delay_days=1 # Friday send, Monday next
    )
    bump_2 = basic_email_sequence_step(
        client_sdr=client_sdr,
        client_archetype=archetype,
        overall_status=ProspectOverallStatus.BUMPED,
        bumped_count=2,
        default=True,
    )

    pst = pytz.timezone('America/Los_Angeles')
    current_date = datetime.now(pst)
    last_sunday = current_date.replace(year=2023, month=10, day=15, hour=9, minute=0, second=0, microsecond=0) # Last Sunday because we offset by 1 day
    this_monday = current_date.replace(year=2023, month=10, day=16, hour=9, minute=0, second=0, microsecond=0)
    this_thursday = current_date.replace(year=2023, month=10, day=19, hour=9, minute=0, second=0, microsecond=0)
    this_friday = current_date.replace(year=2023, month=10, day=20, hour=9, minute=0, second=0, microsecond=0)
    next_monday = current_date.replace(year=2023, month=10, day=23, hour=9, minute=0, second=0, microsecond=0)

    with freeze_time(last_sunday):
        assert EmailMessagingSchedule.query.count() == 0
        ids = populate_email_messaging_schedule_entries(
            client_sdr_id=client_sdr.id,
            prospect_email_id=prospect_email.id,
            subject_line_id=subject_line.id,
            body_id=body.id,
            initial_email_subject_line_template_id=email_subject_line_template.id,
            initial_email_body_template_id=email_body_template.id,
        )
        assert EmailMessagingSchedule.query.count() == 4
        assert len(ids) == 4
        assert EmailMessagingSchedule.query.get(ids[0]).email_type == EmailMessagingType.INITIAL_EMAIL
        assert EmailMessagingSchedule.query.get(ids[0]).date_scheduled.date() == this_monday.date()
        assert EmailMessagingSchedule.query.get(ids[1]).email_type == EmailMessagingType.FOLLOW_UP_EMAIL
        assert EmailMessagingSchedule.query.get(ids[1]).date_scheduled.date() == this_thursday.date()
        assert EmailMessagingSchedule.query.get(ids[2]).email_type == EmailMessagingType.FOLLOW_UP_EMAIL
        assert EmailMessagingSchedule.query.get(ids[2]).date_scheduled.date() == this_friday.date()
        assert EmailMessagingSchedule.query.get(ids[3]).email_type == EmailMessagingType.FOLLOW_UP_EMAIL
        assert EmailMessagingSchedule.query.get(ids[3]).date_scheduled.date() == next_monday.date()


@use_app_context
def test_get_next_available_send_date():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    email_bank = basic_sdr_email_bank(client_sdr)
    schedule = basic_sdr_email_send_schedule(client_sdr, email_bank)

    pst = pytz.timezone('America/Los_Angeles')
    current_date = datetime.now(pst)
    current_date_monday = current_date.replace(year=2023, month=10, day=16, hour=9, minute=0, second=0, microsecond=0)
    tomorrow = current_date_monday + timedelta(days=1) # We use tomorrow because there is logic which, if no emails have been sent, we default to starting TOMORROW
    day_after_tomorrow = current_date_monday + timedelta(days=2)
    next_monday = current_date_monday + timedelta(days=7)

    # Before and after hours
    before_hours = current_date_monday.replace(hour=5)
    after_hours = current_date_monday.replace(hour=22)

    # Weekend
    days_until_saturday = 5 - current_date_monday.weekday()  # 5 for Saturday
    saturday = current_date_monday + timedelta(days=days_until_saturday)

    with freeze_time(before_hours): # No initial message -> bumps up to tomorrow at 9am
        date = get_initial_email_send_date(
            client_sdr_id=client_sdr.id,
            email_bank_id=email_bank.id,
        )
        assert date == tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)

    with freeze_time(after_hours): # No initial message -> bumps up to day after tomorrow at 9am
        date = get_initial_email_send_date(
            client_sdr_id=client_sdr.id,
            email_bank_id=email_bank.id,
        )
        assert date == day_after_tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)

    with freeze_time(saturday): # No initial message -> bumps up to Monday at 9am
        date = get_initial_email_send_date(
            client_sdr_id=client_sdr.id,
            email_bank_id=email_bank.id,
        )
        assert date == next_monday.replace(hour=9, minute=0, second=0, microsecond=0)


@use_app_context
def test_verify_followup_send_date():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    email_bank = basic_sdr_email_bank(client_sdr)
    schedule = basic_sdr_email_send_schedule(client_sdr, email_bank)

    pst = pytz.timezone('America/Los_Angeles')
    current_date = datetime.now(pst)
    current_date_monday = current_date.replace(year=2023, month=10, day=16, hour=9, minute=0, second=0, microsecond=0)
    days_until_saturday = 5 - current_date_monday.weekday()  # 5 for Saturday
    saturday = current_date_monday + timedelta(days=days_until_saturday)
    next_monday = current_date_monday + timedelta(days=7)

    date = verify_followup_send_date(
        client_sdr_id=client_sdr.id,
        followup_send_date=saturday,
        email_bank_id=email_bank.id,
    )
    assert date == next_monday


@use_app_context
@mock.patch("src.message_generation.email.services.generate_email", return_value={"body": "This is the test body."})
def test_generate_email_messaging_schedule_entry(mock_generate_email):
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype)
    prospect_email = basic_prospect_email(prospect)
    email_body_template = basic_email_sequence_step(client_sdr, archetype)
    email_subject_line_template = basic_email_subject_line_template(
        client_sdr, archetype)
    subject_line = basic_generated_message(prospect)
    body = basic_generated_message(prospect)
    email_bank = basic_sdr_email_bank(client_sdr)
    schedule = basic_sdr_email_send_schedule(client_sdr, email_bank)

    bump_accepted = basic_email_sequence_step(
        client_sdr=client_sdr, client_archetype=archetype, overall_status=ProspectOverallStatus.ACCEPTED, default=True)
    bump_1 = basic_email_sequence_step(
        client_sdr=client_sdr, client_archetype=archetype, overall_status=ProspectOverallStatus.BUMPED, bumped_count=1, default=True)
    bump_2 = basic_email_sequence_step(
        client_sdr=client_sdr, client_archetype=archetype, overall_status=ProspectOverallStatus.BUMPED, bumped_count=2, default=True)

    now = datetime.utcnow()

    assert EmailMessagingSchedule.query.count() == 0
    ids = populate_email_messaging_schedule_entries(
        client_sdr_id=client_sdr.id,
        prospect_email_id=prospect_email.id,
        subject_line_id=subject_line.id,
        body_id=body.id,
        initial_email_subject_line_template_id=email_subject_line_template.id,
        initial_email_body_template_id=email_body_template.id,
        initial_email_send_date=now
    )
    first_followup_id = ids[1]

    scheduled_message: EmailMessagingSchedule = EmailMessagingSchedule.query.get(first_followup_id)
    assert scheduled_message.send_status == EmailMessagingStatus.NEEDS_GENERATION
    assert scheduled_message.subject_line_id is None
    assert scheduled_message.body_id is None

    result, _ = generate_email_messaging_schedule_entry(first_followup_id)
    assert result
    assert mock_generate_email.called_once()
    db.session.refresh(scheduled_message)
    scheduled_message: EmailMessagingSchedule = EmailMessagingSchedule.query.get(first_followup_id)
    assert scheduled_message.send_status == EmailMessagingStatus.SCHEDULED
    message: GeneratedMessage = GeneratedMessage.query.get(scheduled_message.subject_line_id)
    assert message
    assert message.completion == f"Re: {subject_line.completion}"

    scheduled_message_2: EmailMessagingSchedule = EmailMessagingSchedule.query.get(ids[2])
    assert scheduled_message_2.send_status == EmailMessagingStatus.NEEDS_GENERATION
    assert scheduled_message_2.subject_line_id is None
    assert scheduled_message_2.body_id is None

    result, _ = generate_email_messaging_schedule_entry(ids[2])
    assert result
    assert mock_generate_email.called_twice()
    db.session.refresh(scheduled_message_2)
    scheduled_message_2: EmailMessagingSchedule = EmailMessagingSchedule.query.get(ids[2])
    assert scheduled_message_2.send_status == EmailMessagingStatus.SCHEDULED
    message_2: GeneratedMessage = GeneratedMessage.query.get(scheduled_message_2.subject_line_id)
    assert message_2
    assert message_2.completion == f"Re: {message.completion}"

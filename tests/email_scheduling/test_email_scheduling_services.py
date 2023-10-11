from datetime import datetime, timedelta
from app import db, app
from src.email_scheduling.models import EmailMessagingSchedule, EmailMessagingStatus, EmailMessagingType
from src.email_scheduling.services import DEFAULT_SENDING_DELAY_INTERVAL, create_email_messaging_schedule_entry, populate_email_messaging_schedule_entries
from src.prospecting.models import ProspectOverallStatus
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_prospect,
    basic_prospect_email,
    basic_archetype,
    basic_email_sequence_step,
    basic_email_subject_line_template,
    basic_generated_message
)
from decorators import use_app_context


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
    email_body_template = basic_email_sequence_step(client_sdr, archetype)
    email_subject_line_template = basic_email_subject_line_template(
        client_sdr, archetype)
    subject_line = basic_generated_message(prospect)
    body = basic_generated_message(prospect)

    bump_accepted = basic_email_sequence_step(
        client_sdr=client_sdr, client_archetype=archetype, overall_status=ProspectOverallStatus.ACCEPTED)
    bump_1 = basic_email_sequence_step(
        client_sdr=client_sdr, client_archetype=archetype, overall_status=ProspectOverallStatus.BUMPED, bumped_count=1)
    bump_2 = basic_email_sequence_step(
        client_sdr=client_sdr, client_archetype=archetype, overall_status=ProspectOverallStatus.BUMPED, bumped_count=2)

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
    assert EmailMessagingSchedule.query.count() == 4
    assert len(ids) == 4
    assert EmailMessagingSchedule.query.get(ids[0]).email_type == EmailMessagingType.INITIAL_EMAIL
    assert EmailMessagingSchedule.query.get(ids[0]).date_scheduled == now
    assert EmailMessagingSchedule.query.get(ids[1]).email_type == EmailMessagingType.FOLLOW_UP_EMAIL
    assert EmailMessagingSchedule.query.get(ids[1]).date_scheduled == now + timedelta(DEFAULT_SENDING_DELAY_INTERVAL)
    assert EmailMessagingSchedule.query.get(ids[2]).email_type == EmailMessagingType.FOLLOW_UP_EMAIL
    assert EmailMessagingSchedule.query.get(ids[2]).date_scheduled == now + timedelta(DEFAULT_SENDING_DELAY_INTERVAL * 2)
    assert EmailMessagingSchedule.query.get(ids[3]).email_type == EmailMessagingType.FOLLOW_UP_EMAIL
    assert EmailMessagingSchedule.query.get(ids[3]).date_scheduled == now + timedelta(DEFAULT_SENDING_DELAY_INTERVAL * 3)

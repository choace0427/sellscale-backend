from app import app, db
from datetime import time
from tests.test_utils.decorators import use_app_context
from src.client.sdr.email.models import EmailType, SDREmailBank, SDREmailSendSchedule
from src.client.sdr.email.services_email_schedule import create_sdr_email_send_schedule, update_sdr_email_send_schedule
from tests.test_utils.test_utils import (
    basic_sdr_email_send_schedule,
    test_app,
    basic_client,
    basic_client_sdr,
    basic_sdr_email_bank,
)


@use_app_context
def test_create_sdr_email_send_schedule():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    email_bank = basic_sdr_email_bank(client_sdr)

    assert SDREmailSendSchedule.query.count() == 0
    id = create_sdr_email_send_schedule(
        client_sdr_id = client_sdr.id,
        email_bank_id = email_bank.id,
        time_zone = "America/New_York",
        days = [1, 2, 3, 4, 5],
        start_time = time(hour=9),
        end_time = time(hour=17),
    )
    assert SDREmailSendSchedule.query.count() == 1
    assert SDREmailSendSchedule.query.first().id == id


@use_app_context
def test_update_sdr_email_send_schedule():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    email_bank = basic_sdr_email_bank(client_sdr)
    email_send_schedule = basic_sdr_email_send_schedule(client_sdr, email_bank)

    assert email_send_schedule.time_zone == "America/New_York"
    success = update_sdr_email_send_schedule(
        client_sdr_id = client_sdr.id,
        send_schedule_id = email_send_schedule.id,
        time_zone = "America/Los_Angeles",
    )
    assert success
    assert email_send_schedule.time_zone == "America/Los_Angeles"

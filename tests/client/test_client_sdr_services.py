from datetime import datetime
from app import app, db
from decorators import use_app_context
from src.client.models import SLASchedule
from src.client.sdr.services_client_sdr import create_sla_schedule, get_sdr_blacklist_words, get_sla_schedules_for_sdr, load_sla_schedules, update_sdr_blacklist_words, update_sla_schedule
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
)
from freezegun import freeze_time



@use_app_context
def test_update_sdr_blacklist_words():
    client = basic_client()
    sdr = basic_client_sdr(client)
    blacklist_words = ["word1", "word2", "word3"]

    assert sdr.blacklisted_words == None
    update_sdr_blacklist_words(sdr.id, blacklist_words)
    assert sdr.blacklisted_words == blacklist_words


@use_app_context
def test_get_sdr_blacklist_words():
    client = basic_client()
    sdr = basic_client_sdr(client)
    blacklist_words = ["word1", "word2", "word3"]

    assert sdr.blacklisted_words == None
    update_sdr_blacklist_words(sdr.id, blacklist_words)
    assert sdr.blacklisted_words == blacklist_words

    assert get_sdr_blacklist_words(sdr.id) == blacklist_words


@use_app_context
def test_create_sla_schedule():
    client = basic_client()
    sdr = basic_client_sdr(client)

    # Creating SLA schedule with random date will grab the Monday and Friday of that week
    monday = datetime(2023, 9, 11)
    today = datetime(2023, 9, 13)
    friday = datetime(2023, 9, 15)
    schedule_id = create_sla_schedule(
        client_sdr_id=sdr.id,
        start_date=today,
    )
    schedule: SLASchedule = SLASchedule.query.get(schedule_id)
    assert schedule.client_sdr_id == sdr.id
    assert schedule.start_date == monday
    assert schedule.end_date == friday


@use_app_context
def test_get_sla_schedules_for_sdr():
    client = basic_client()
    sdr = basic_client_sdr(client)

    nine_four = datetime(2023, 9, 4)
    nine_eleven = datetime(2023, 9, 11)
    nine_eighteen = datetime(2023, 9, 18)

    schedule_id_94 = create_sla_schedule(
        client_sdr_id=sdr.id,
        start_date=nine_four,
    )
    schedule_id_911 = create_sla_schedule(
        client_sdr_id=sdr.id,
        start_date=nine_eleven,
    )
    schedule_id_918 = create_sla_schedule(
        client_sdr_id=sdr.id,
        start_date=nine_eighteen,
    )

    # Get all schedules
    schedules = get_sla_schedules_for_sdr(
        client_sdr_id=sdr.id,
    )
    assert len(schedules) == 3
    assert schedules[0].get('id') == schedule_id_918
    assert schedules[1].get('id') == schedule_id_911
    assert schedules[2].get('id') == schedule_id_94

    # Get schedules start after 9/11
    schedules = get_sla_schedules_for_sdr(
        client_sdr_id=sdr.id,
        start_date=nine_eleven,
    )
    assert len(schedules) == 2
    assert schedules[0].get('id') == schedule_id_918
    assert schedules[1].get('id') == schedule_id_911

    # Get schedules that end before 9/11
    schedules = get_sla_schedules_for_sdr(
        client_sdr_id=sdr.id,
        end_date=nine_eleven,
    )
    assert len(schedules) == 1
    assert schedules[0].get('id') == schedule_id_94

    # Get schedule that starts after 9/11 and ends before 9/18
    schedules = get_sla_schedules_for_sdr(
        client_sdr_id=sdr.id,
        start_date=nine_eleven,
        end_date=nine_eighteen,
    )
    assert len(schedules) == 1
    assert schedules[0].get('id') == schedule_id_911


@use_app_context
def test_update_sla_schedule():
    client = basic_client()
    sdr = basic_client_sdr(client)

    nine_four = datetime(2023, 9, 4)

    schedule_id = create_sla_schedule(
        client_sdr_id=sdr.id,
        start_date=nine_four,
    )

    # Update the schedule, using the Schedule ID
    success, _ = update_sla_schedule(
        client_sdr_id=sdr.id,
        sla_schedule_id=schedule_id,
        linkedin_volume=100,
        email_volume=200,
    )
    assert success
    schedule: SLASchedule = SLASchedule.query.get(schedule_id)
    assert schedule.linkedin_volume == 100
    assert schedule.email_volume == 200

    # Update the schedule, using the start date
    success, _ = update_sla_schedule(
        client_sdr_id=sdr.id,
        start_date=nine_four,
        linkedin_volume=300,
        email_volume=400,
    )
    assert success
    schedule: SLASchedule = SLASchedule.query.get(schedule_id)
    assert schedule.linkedin_volume == 300
    assert schedule.email_volume == 400


@use_app_context
def test_load_sla_schedules():
    client = basic_client()
    sdr_no_schedules = basic_client_sdr(client)
    sdr_1_schedule = basic_client_sdr(client)
    sdr_3_schedules = basic_client_sdr(client)

    # Freeze time to be Monday, September 4th, 2023
    with freeze_time(datetime(2023, 9, 4)):

         # Load schedule for NO schedules
        schedules: list[SLASchedule] = SLASchedule.query.filter_by(client_sdr_id=sdr_no_schedules.id).all()
        assert len(schedules) == 0
        success, new_schedule_ids = load_sla_schedules(sdr_no_schedules.id)
        assert success
        assert len(new_schedule_ids) == 3
        schedules: list[SLASchedule] = SLASchedule.query.filter_by(client_sdr_id=sdr_no_schedules.id).order_by(SLASchedule.start_date.desc()).all()
        assert len(schedules) == 3
        assert schedules[0].start_date == datetime(2023, 9, 18)
        assert schedules[1].start_date == datetime(2023, 9, 11)
        assert schedules[2].start_date == datetime(2023, 9, 4)

        # Load schedule for 1 schedule (needs 2 more)
        create_sla_schedule(
            client_sdr_id=sdr_1_schedule.id,
            start_date=datetime(2023, 9, 4),
        )
        schedules: list[SLASchedule] = SLASchedule.query.filter_by(client_sdr_id=sdr_1_schedule.id).all()
        assert len(schedules) == 1
        success, new_schedule_ids = load_sla_schedules(sdr_1_schedule.id)
        assert success
        assert len(new_schedule_ids) == 2
        schedules: list[SLASchedule] = SLASchedule.query.filter_by(client_sdr_id=sdr_1_schedule.id).order_by(SLASchedule.start_date.desc()).all()
        print([schedule.to_dict() for schedule in schedules], new_schedule_ids)
        assert len(schedules) == 3
        assert schedules[0].id in new_schedule_ids
        assert schedules[1].id in new_schedule_ids
        assert schedules[2].id not in new_schedule_ids
        assert schedules[0].start_date == datetime(2023, 9, 18)
        assert schedules[1].start_date == datetime(2023, 9, 11)
        assert schedules[2].start_date == datetime(2023, 9, 4)

        # Load schedule for 3 schedules (needs 0 more)
        create_sla_schedule(
            client_sdr_id=sdr_3_schedules.id,
            start_date=datetime(2023, 9, 4),
        )
        create_sla_schedule(
            client_sdr_id=sdr_3_schedules.id,
            start_date=datetime(2023, 9, 11),
        )
        create_sla_schedule(
            client_sdr_id=sdr_3_schedules.id,
            start_date=datetime(2023, 9, 18),
        )
        schedules: list[SLASchedule] = SLASchedule.query.filter_by(client_sdr_id=sdr_3_schedules.id).all()
        assert len(schedules) == 3
        success, new_schedule_ids = load_sla_schedules(sdr_3_schedules.id)
        assert success
        assert len(new_schedule_ids) == 0
        schedules: list[SLASchedule] = SLASchedule.query.filter_by(client_sdr_id=sdr_3_schedules.id).order_by(SLASchedule.start_date.desc()).all()
        assert len(schedules) == 3

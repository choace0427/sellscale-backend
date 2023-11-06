from src.utils.random_string import *
from app import db
import mock
from src.utils.request_helpers import get_request_parameter, get_auth_token
from datetime import datetime, date, timedelta, timezone
from src.utils.datetime.dateparse_utils import *
from src.utils.datetime.dateutils import (
    seconds_between_datelike,
    datetime_to_seconds,
    now_in_utc,
    datetime_interval_generator,
)
from freezegun import freeze_time


def test_convert_string_to_datetime_or_none():
    assert convert_string_to_datetime_or_none(None) == None
    assert convert_string_to_datetime_or_none("2020-01-01") == datetime(
        2020, 1, 1, 0, 0
    )


def test_seconds_between_datelike():
    assert (
        seconds_between_datelike(
            datetime(2020, 1, 1), datetime(2020, 1, 2)
        )
        == 86400.0
    )
    assert (
        seconds_between_datelike(date(2020, 1, 1), date(2020, 1, 2))
        == 86400.0
    )


def test_datetime_to_seconds():
    assert datetime_to_seconds(datetime(2020, 1, 1)) == 1577836800.0
    assert datetime_to_seconds(date(2020, 1, 1)) == 1577836800.0


@freeze_time("2020-01-01")
def test_now_in_utc():
    assert now_in_utc() == datetime(2020, 1, 1, 0, 0)
    assert now_in_utc(tz_aware=True) == datetime(
        2020, 1, 1, 0, 0, tzinfo=timezone.utc
    )


@freeze_time("2020-01-01")
def test_datetime_interval_generator():
    start = datetime(2020, 1, 1)
    end = datetime(2020, 1, 3)
    delta = timedelta(days=1)
    interval = datetime_interval_generator(start, end, delta)
    assert next(interval) == datetime(2020, 1, 1)
    assert next(interval) == datetime(2020, 1, 2)
    assert next(interval, None) == None


def test_get_working_hours_in_utc():
    start_time, end_time = get_working_hours_in_utc(
        timezone_string="America/Los_Angeles"
    )
    now = datetime.now(timezone.utc)
    assert start_time == now.replace(hour=16, minute=0, second=0, microsecond=0)
    assert end_time == start_time + timedelta(hours=8)

@freeze_time("2020-01-01")
def test_is_weekend():
    assert is_weekend(timezone_string="America/Los_Angeles") == False

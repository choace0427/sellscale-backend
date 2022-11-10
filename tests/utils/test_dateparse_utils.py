from src.utils.random_string import *
from app import db
import mock
from src.utils.request_helpers import get_request_parameter, get_auth_token
import datetime
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
    assert convert_string_to_datetime_or_none("2020-01-01") == datetime.datetime(
        2020, 1, 1, 0, 0
    )


def test_seconds_between_datelike():
    assert (
        seconds_between_datelike(
            datetime.datetime(2020, 1, 1), datetime.datetime(2020, 1, 2)
        )
        == 86400.0
    )
    assert (
        seconds_between_datelike(datetime.date(2020, 1, 1), datetime.date(2020, 1, 2))
        == 86400.0
    )


def test_datetime_to_seconds():
    assert datetime_to_seconds(datetime.datetime(2020, 1, 1)) == 1577836800.0
    assert datetime_to_seconds(datetime.date(2020, 1, 1)) == 1577836800.0


@freeze_time("2020-01-01")
def test_now_in_utc():
    assert now_in_utc() == datetime.datetime(2020, 1, 1, 0, 0)
    assert now_in_utc(tz_aware=True) == datetime.datetime(
        2020, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
    )


@freeze_time("2020-01-01")
def test_datetime_interval_generator():
    start = datetime.datetime(2020, 1, 1)
    end = datetime.datetime(2020, 1, 3)
    delta = datetime.timedelta(days=1)
    interval = datetime_interval_generator(start, end, delta)
    assert next(interval) == datetime.datetime(2020, 1, 1)
    assert next(interval) == datetime.datetime(2020, 1, 2)
    assert next(interval, None) == None

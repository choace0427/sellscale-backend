import datetime
from datetime import date, datetime, timedelta
from typing import Union

import pytz

epoch = datetime.utcfromtimestamp(0)


def seconds_between_datelike(dt1: Union[date, datetime], dt2: Union[date, datetime]):
    return (dt2 - dt1).total_seconds()


def datetime_to_seconds(dt: Union[date, datetime]):
    if isinstance(dt, datetime):
        return seconds_between_datelike(epoch, dt)

    return seconds_between_datelike(epoch.date(), dt)


def now_in_utc(tz_aware: bool = False):
    if not tz_aware:
        return datetime.utcnow()
    else:
        return datetime.now(tz=pytz.utc)


def datetime_interval_generator(start: datetime, end: datetime, delta: timedelta):
    curr = start
    while curr < end:
        yield curr
        curr += delta


def get_current_month():
    return datetime.now().month


def get_current_year():
    return datetime.now().year

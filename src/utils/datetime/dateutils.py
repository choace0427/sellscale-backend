from datetime import datetime, timedelta
import datetime
from datetime import date, datetime, timedelta
from typing import Union, Optional

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


def get_datetime_now():
    return datetime.now()


def get_current_month():
    return datetime.now().month


def get_current_year():
    return datetime.now().year


def get_next_next_monday_sunday(
    date: Optional[datetime],
) -> tuple[datetime.date, datetime.date]:
    date = date or datetime.today()

    days_until_next_monday = (7 - date.weekday()) % 7
    if days_until_next_monday == 0:  # If today is Monday
        days_until_next_monday = 7
    next_monday = date + timedelta(days=days_until_next_monday)
    next_next_monday = next_monday + timedelta(days=7)
    next_next_sunday = next_next_monday + timedelta(days=6)

    return next_next_monday.date(), next_next_sunday.date()


def get_current_monday_sunday(
    date: Optional[datetime],
) -> tuple[datetime.date, datetime.date]:
    date = date or datetime.today()

    # Get the monday of the current week
    start_date = date - timedelta(days=date.weekday())

    # Get the sunday of the current week
    end_date = start_date + timedelta(days=6)

    return start_date.date(), end_date.date()


def get_current_monday_friday(
    date: Optional[datetime],
) -> tuple[datetime.date, datetime.date]:
    date = date or datetime.today()

    # Get the monday of the current week
    start_date = date - timedelta(days=date.weekday())

    # Get the friday of the current week
    end_date = start_date + timedelta(days=4)

    return start_date.date(), end_date.date()


def get_future_datetime(
    months=0, days=0, minutes=0, start_time: datetime = datetime.utcnow()
):
    # Calculate the future time by adding the specified months, days, and minutes
    future_time = start_time + timedelta(
        days=days,
        minutes=minutes,
        # Adding months is a bit more complicated due to varying month lengths
        # We'll add the months one by one
    )

    # Handle the months increment
    if months > 0:
        for _ in range(months):
            # Calculate the number of days in the current month
            days_in_current_month = (
                future_time.replace(day=1) + timedelta(days=32)
            ).day - 1
            # Add the days of the current month to the future_time
            future_time += timedelta(days=days_in_current_month)

    return future_time

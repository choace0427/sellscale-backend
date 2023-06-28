from typing import Optional

import dateparser
import pytz
from datetime import datetime, time


def convert_string_to_datetime_or_none(content: Optional[str]):
    if not content:
        return None

    return convert_string_to_datetime(content)


def convert_string_to_datetime(content: str):
    return dateparser.parse(
        content
    )  # TODO: Hardcode options to preferred parsing options to avoid settings.yaml dependencies.


def get_working_hours_in_utc(timezone_string: str) -> tuple[datetime, datetime]:
    """Gets the working hours in UTC for a given timezone. 9am to 5pm.

    Args:
        timezone_string (str): The timezone to get the working hours for.

    Returns:
        tuple[datetime, datetime]: The working hours in UTC.
    """
    # Convert the timezone string to a pytz timezone object
    timezone = pytz.timezone(timezone_string)

    # Get the current date and time in the specified timezone
    current_time = datetime.now(timezone)

    # Create a datetime object for today with the desired working hours
    today_working_hours_start = timezone.localize(datetime.combine(current_time.date(), time(9)))
    today_working_hours_end = timezone.localize(datetime.combine(current_time.date(), time(17)))

    # Convert the working hours to UTC
    utc_working_hours_start = today_working_hours_start.astimezone(pytz.UTC)
    utc_working_hours_end = today_working_hours_end.astimezone(pytz.UTC)

    return utc_working_hours_start, utc_working_hours_end

def is_weekend(timezone_string: str) -> bool:
    """Checks if the current day is a weekend day in a given timezone.

    Args:
        timezone_string (str): The timezone to check.

    Returns:
        bool: A boolean indicating if the current day is a weekend day.
    """
    # Convert the timezone string to a pytz timezone object
    timezone = pytz.timezone(timezone_string)

    # Get the current date and time in the specified timezone
    current_time = datetime.now(timezone)

    # Get the weekday of the current date (Monday: 0, Tuesday: 1, ..., Sunday: 6)
    weekday = current_time.weekday()

    # Check if the weekday is Saturday (5) or Sunday (6)
    if weekday == 5 or weekday == 6:
        return True
    else:
        return False

from datetime import datetime
from enum import Enum


class DateFormat(Enum):
    YYYY_MM_DD = '%Y-%m-%d'
    MM_DD_YY_SLASH = '%m/%d/%Y'


def format_datestring(dt: datetime, format_code: DateFormat):
    return dt.strftime(format_code.value)

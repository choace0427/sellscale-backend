from datetime import datetime
from typing import Any, Dict

import pytz

from src.utils.abstract.attr_utils import deep_get
from src.utils.converters.base_converter import BaseConverter
from src.utils.datetime.dateparse_utils import convert_string_to_datetime

STABLE_SRC_FMT_KEY = 'src_fmt'
UNSTABLE_SRC_FMT_KEY = 'unstable_src_fmts'

DATE_MAPPER_KEY = 'date_mapper'


class ModeledDateToTimestampProtoString(BaseConverter):
    def __init__(self, dependencies: Dict[str, str]):
        super().__init__(dependencies)
        self._date_mapper: dict = dependencies[DATE_MAPPER_KEY]

    def convert(self, value: Any) -> Any:
        if not value:
            return None
        value = {'value': value}
        required_args = {'year': 1900, 'month': 1, 'day': 1}
        target_args = {
            k: deep_get(value, v['_name']) for (k, v) in self._date_mapper.items()
        }

        required_args.update({k: v for k, v in target_args.items() if bool(v)})
        dt = datetime(**required_args)
        dt = dt.replace(tzinfo=pytz.UTC)
        return dt.isoformat()


class StringToTimestampProtoString(BaseConverter):
    """Attempts to convert a string to a timestamp proto string.

    WARNING. Performance issues with the dateparse module, use the site below to determine the dateformat code if it is available.
    http://www.strfti.me/
    """

    def __init__(self, dependencies: Dict[str, str]):
        super().__init__(dependencies)
        if STABLE_SRC_FMT_KEY in self._dependencies:
            self._src_fmts = [self._dependencies[STABLE_SRC_FMT_KEY]]
        elif STABLE_SRC_FMT_KEY in self._dependencies:
            self._src_fmts = self._dependencies.get(UNSTABLE_SRC_FMT_KEY)
        else:
            self._src_fmts = None

    def convert(self, value: Any) -> Any:
        if self._src_fmts:
            dt = None
            for fmt in self._src_fmts:
                try:
                    dt = datetime.strptime(value, fmt)
                    break
                except ValueError:
                    pass

            if not dt:
                raise ValueError(f'{value} did not match any formats: {self._src_fmts}')

        else:
            dt = convert_string_to_datetime(value)

        dt = dt.replace(tzinfo=pytz.UTC)
        return dt.isoformat()

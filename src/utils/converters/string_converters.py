from enum import Enum
from typing import Any

from src.utils.converters.base_converter import BaseConverter
from src.utils.jinja.utils import render_jinja

_CASING_KEY = "casing"
_FMT_KEY = "jinja"


class Casing(Enum):
    LOWER = "LOWER"
    UPPER = "UPPER"
    CAPITALIZED = "CAPITALIZED"


class RecaseConverter(BaseConverter):
    def convert(self, value: Any) -> Any:
        casing = self._dependencies[_CASING_KEY]

        if casing == Casing.LOWER.value:
            return value.lower()
        elif casing == Casing.UPPER.value:
            return value.upper()
        elif casing == Casing.CAPITALIZED.value:
            return value.capitalize()

        return value


class JinjaConverter(BaseConverter):
    def convert(self, value: Any) -> Any:
        jinja_format_string = self._dependencies[_FMT_KEY]

        return render_jinja(jinja_format_string, {"value": value})


def sanitize_string(text: str) -> str:
    return (
        text.replace('"', "").replace("\n", "\\n").replace("\r", "").replace("\\", "")
    )

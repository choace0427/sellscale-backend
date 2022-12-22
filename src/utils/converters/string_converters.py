from enum import Enum
from typing import Any
import re

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


def sanitize_full_name_for_processing(full_name: str):
    if not full_name:
        return None
    full_name = full_name.split(",")[0]

    words = full_name.split(" ")
    word_length = len(words)
    title_index = 0
    if word_length > 2:
        for i, word in enumerate(words):
            if words[i].isupper():
                title_index = i
                break
        if title_index > 1:
            words = words[0:title_index]
    full_name = " ".join(words)

    titles = ["Dr.", "Dr "]
    for t in titles:
        full_name = full_name.replace(t, "")

    # remove anything in parenthesis
    pattern = re.compile(r"\(.*\)")
    full_name = pattern.sub("", full_name)

    # remove anything that is not a letter
    full_name = re.sub(r"[^a-zA-Z]", " ", full_name)

    # remove extra spaces
    full_name = " ".join(full_name.split())

    return full_name


def needs_title_casing(name: str):
    if name.isupper():
        return True
    if name.islower():
        return True
    return False


def get_first_name_from_full_name(full_name: str):
    full_name = sanitize_full_name_for_processing(full_name=full_name)
    if not full_name:
        return None
    spl = full_name.split(" ")
    if len(spl) == 0:
        return None
    name = spl[0]
    if needs_title_casing(name):
        name = name.title()

    return name


def get_last_name_from_full_name(full_name: str):
    full_name = sanitize_full_name_for_processing(full_name=full_name)
    if not full_name:
        return None
    spl = full_name.split(" ")
    if len(spl) <= 1:
        return None

    # In case there's a 1 initial middle name
    if len(spl) == 3:
        name = spl[2]
    else:
        name = spl[1]
    if needs_title_casing(name):
        name = name.title()

    return name

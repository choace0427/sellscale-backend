from typing import Optional

import dateparser


def convert_string_to_datetime_or_none(content: Optional[str]):
    if not content:
        return None

    return convert_string_to_datetime(content)


def convert_string_to_datetime(content: str):
    return dateparser.parse(
        content
    )  # TODO: Hardcode options to preferred parsing options to avoid settings.yaml dependencies.

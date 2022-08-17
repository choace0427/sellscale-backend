from typing import Dict

import src.utils.converters.all_converters as _
from src.utils.abstract.class_utils import get_all_subclasses
from src.utils.converters.base_converter import BaseConverter

all_converters = list(get_all_subclasses(BaseConverter))

all_converters_map: Dict[str, BaseConverter] = dict(
    (clz.__name__, clz) for clz in all_converters
)


def provide_converter(clazz_str: str, dependencies: dict) -> BaseConverter:
    try:
        return all_converters_map[clazz_str](dependencies)
    except KeyError as err:
        raise ValueError(f'No Converter Found for {clazz_str}') from err

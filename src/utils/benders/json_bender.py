from typing import Any, Iterable, List

from src.utils.abstract.attr_utils import deep_set, deep_get
from src.utils.converters.converter_library import provide_converter


class JsonBender:
    def __init__(self, bender_dict: dict) -> None:
        self._bender_dict = bender_dict
        if 'vars' in self._bender_dict:
            del self._bender_dict['vars']

    def _bend_single_item(self, target_path: str, bender: dict, src: dict) -> Any:
        if '_value' in bender:
            value = bender['_value']
        elif '_name' in bender:
            key = bender['_name']
            try:
                value = deep_get(src, key, None)
            except TypeError as e:
                raise ValueError(f'Error parsing type path for {key}') from e
        else:
            raise ValueError(
                f'Must specify one of "_value" or "_name" for {target_path}'
            )

        if '_list' in bender:
            subbender = bender['_list']
            value = value or []
            if '_name' in subbender:
                value = list(map(lambda x: x.get(subbender['_name']), value))
            else:
                value = JsonBender(bender['_list']).bend_list(value)

        if '_converters' in bender:
            for converter in bender['_converters']:
                converter_name: str = converter['clazz']
                dependencies = converter.get('_dependencies', {})

                converter = provide_converter(converter_name, dependencies)
                value = converter.convert(value)

        return value

    def bend(self, target: dict) -> dict:
        result = {}

        for target_path, bender in self._bender_dict.items():
            deep_set(
                result, target_path, self._bend_single_item(target_path, bender, target)
            )

        return result

    def bend_list(self, target: Iterable[dict]) -> List[dict]:
        return [self.bend(x) for x in target]

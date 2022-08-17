from typing import Any, Dict

from src.utils.converters.base_converter import BaseConverter

_KEY_TO_EXTRACT = 'extract_key'


class FlatMapConverter(BaseConverter):
    def __init__(self, dependencies: Dict[str, str]):
        super().__init__(dependencies)
        self._extract_key = self._dependencies.get(_KEY_TO_EXTRACT)

    def convert(self, value: Any) -> Any:
        if self._extract_key:
            value = map(lambda x: x.get(self._extract_key), value)

        return sum(value, [])

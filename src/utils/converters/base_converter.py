from abc import abstractmethod
from typing import Any, Dict


class BaseConverter:
    def __init__(self, dependencies: Dict[str, str]):
        self._dependencies = dependencies

    @abstractmethod
    def convert(self, value: Any) -> Any:
        pass

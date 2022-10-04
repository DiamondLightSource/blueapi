from pathlib import Path
from typing import Any, Generic, Mapping, Type, TypeVar

import yaml
from apischema import deserialize

#: Configuration schema dataclass
C = TypeVar("C")


class ConfigLoader(Generic[C]):
    _schema: Type[C]
    _values: Mapping[str, Any]

    def __init__(self, schema: Type[C]) -> None:
        self._schema = schema
        self._values = {}

    def use_values(self, values: Mapping[str, Any]) -> None:
        self._values = {**self._values, **values}

    def use_yaml_or_json_file(self, path: Path) -> None:
        with path.open("r") as stream:
            values = yaml.load(stream, yaml.Loader)
        self.use_values(values)

    def load(self) -> C:
        return deserialize(self._schema, self._values)

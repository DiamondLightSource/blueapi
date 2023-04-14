from pathlib import Path
from typing import Any, Generic, Mapping, Type, TypeVar

import yaml
from pydantic import BaseModel, parse_obj_as

#: Configuration schema dataclass
C = TypeVar("C", bound=BaseModel)


class ConfigLoader(Generic[C]):
    """
    Small utility class for loading config from various sources.
    You must define a config schema as a dataclass (or series of
    nested dataclasses) that can then be loaded from some combination
    of default values, dictionaries, YAML/JSON files etc.
    """

    _schema: Type[C]
    _values: Mapping[str, Any]

    def __init__(self, schema: Type[C]) -> None:
        self._schema = schema
        self._values = {}

    def use_values(self, values: Mapping[str, Any]) -> None:
        """
        Use all values provided in the config, override any defaults
        and values set by previous calls into this class.

        Args:
            values (Mapping[str, Any]): Dictionary of override values,
                                        does not need to be exaustive
                                        if defaults provided.
        """

        self._values = {**self._values, **values}

    def use_yaml_or_json_file(self, path: Path) -> None:
        """
        Use all values provided in the YAML/JSON file in the
        config, override any defaults and values set by
        previous calls into this class.

        Args:
            path (Path): Path to YAML/JSON file
        """

        with path.open("r") as stream:
            values = yaml.load(stream, yaml.Loader)
        self.use_values(values)

    def load(self) -> C:
        """
        Finalize and load the config as an instance of the `schema`
        dataclass.

        Returns:
            C: Dataclass instance holding config
        """

        return parse_obj_as(self._schema, self._values)

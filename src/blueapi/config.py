from pathlib import Path
from pprint import pformat
from typing import Any, Generic, Mapping, Type, TypeVar, Union

import yaml
from pydantic import BaseModel, Field, ValidationError, parse_obj_as

from blueapi.utils import BlueapiBaseModel, InvalidConfigError

DEFAULT_YAML_PATH = Path("src/blueapi_config.yaml")


class StompConfig(BlueapiBaseModel):
    """
    Config for connecting to stomp broker
    """

    host: str = "localhost"
    port: int = 61613


class EnvironmentConfig(BlueapiBaseModel):
    """
    Config for the RunEngine environment
    """

    startup_script: Union[Path, str] = "blueapi.startup.example"


class LoggingConfig(BlueapiBaseModel):
    level: str = "INFO"


class ApplicationConfig(BlueapiBaseModel):
    """
    Config for the worker application as a whole. Root of
    config tree.
    """

    stomp: StompConfig = Field(default_factory=StompConfig)
    env: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


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

    def load_from_yaml(self, path: Path) -> C:
        """
        Use all values provided in a YAML/JSON file in the
        config, override any defaults and values set by
        previous calls into this class.

        Args:
            path (Path): Path to YAML/JSON file
        """

        with path.open("r") as stream:
            values = yaml.load(stream, yaml.Loader)
        self.use_values(values)

        return self.load()

    def load(self) -> C:
        """
        Finalize and load the config as an instance of the `schema`
        dataclass.

        Returns:
            C: Dataclass instance holding config
        """

        try:
            return parse_obj_as(self._schema, self._values)
        except ValidationError:
            raise InvalidConfigError(
                "File passed in does not match the specified"
                + f" schema: \n {pformat(self._schema.schema())}"
            )

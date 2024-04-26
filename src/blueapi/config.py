import os
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import Any, Generic, Literal, TypeVar

import yaml
from pydantic import BaseModel, Field, ValidationError, parse_obj_as, validator

from blueapi.utils import BlueapiBaseModel, InvalidConfigError

LogLevel = Literal["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class SourceKind(str, Enum):
    PLAN_FUNCTIONS = "planFunctions"
    DEVICE_FUNCTIONS = "deviceFunctions"
    DODAL = "dodal"


class Source(BaseModel):
    kind: SourceKind
    module: Path | str


class BasicAuthentication(BaseModel):
    """
    Log in details for when a server uses authentication.
    If username or passcode match exactly the regex ^\\${(.*)}$
    they attempt to replace with an environment variable of the same.
    i.e. ${foo} or ${FOO} are replaced with the value of FOO
    """

    username: str = "guest"
    passcode: str = "guest"

    @validator("username", "passcode")
    def get_from_env(cls, v: str):
        if v.startswith("${") and v.endswith("}"):
            return os.environ[v.removeprefix("${").removesuffix("}").upper()]
        return v


class StompConfig(BaseModel):
    """
    Config for connecting to stomp broker
    """

    host: str = "localhost"
    port: int = 61613
    auth: BasicAuthentication | None = None


class DataWritingConfig(BlueapiBaseModel):
    visit_service_url: str | None = None  # e.g. "http://localhost:8088/api"
    visit_directory: Path = Path("/tmp/0-0")
    group_name: str = "example"


class WorkerEventConfig(BlueapiBaseModel):
    """
    Config for event broadcasting via the message bus
    """

    broadcast_status_events: bool = True


class EnvironmentConfig(BlueapiBaseModel):
    """
    Config for the RunEngine environment
    """

    sources: list[Source] = [
        Source(
            kind=SourceKind.DEVICE_FUNCTIONS, module="blueapi.startup.example_devices"
        ),
        Source(kind=SourceKind.PLAN_FUNCTIONS, module="blueapi.startup.example_plans"),
        Source(kind=SourceKind.PLAN_FUNCTIONS, module="dls_bluesky_core.plans"),
        Source(kind=SourceKind.PLAN_FUNCTIONS, module="dls_bluesky_core.stubs"),
    ]
    data_writing: DataWritingConfig = Field(default_factory=DataWritingConfig)
    events: WorkerEventConfig = Field(default_factory=WorkerEventConfig)


class LoggingConfig(BlueapiBaseModel):
    level: LogLevel = "INFO"


class RestConfig(BlueapiBaseModel):
    host: str = "localhost"
    port: int = 8000
    protocol: str = "http"


class ApplicationConfig(BlueapiBaseModel):
    """
    Config for the worker application as a whole. Root of
    config tree.
    """

    stomp: StompConfig | None = None
    env: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    api: RestConfig = Field(default_factory=RestConfig)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ApplicationConfig):
            return (
                (self.stomp == other.stomp)
                & (self.env == other.env)
                & (self.logging == other.logging)
                & (self.api == other.api)
            )
        return False


C = TypeVar("C", bound=BaseModel)


class ConfigLoader(Generic[C]):
    """
    Small utility class for loading config from various sources.
    You must define a config schema as a dataclass (or series of
    nested dataclasses) that can then be loaded from some combination
    of default values, dictionaries, YAML/JSON files etc.
    """

    _schema: type[C]
    _values: dict[str, Any]

    def __init__(self, schema: type[C]) -> None:
        self._schema = schema
        self._values = {}

    def use_values(self, values: Mapping[str, Any]) -> None:
        """
        Use all values provided in the config, override any defaults
        and values set by previous calls into this class.

        Args:
            values (Mapping[str, Any]): Dictionary of override values,
                                        does not need to be exhaustive
                                        if defaults provided.
        """

        def recursively_update_map(old: dict[str, Any], new: Mapping[str, Any]) -> None:
            for key in new:
                if (
                    key in old
                    and isinstance(old[key], dict)
                    and isinstance(new[key], dict)
                ):
                    recursively_update_map(old[key], new[key])
                else:
                    old[key] = new[key]

        recursively_update_map(self._values, values)

    def use_values_from_yaml(self, path: Path) -> None:
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

    def load(self) -> C:
        """
        Finalize and load the config as an instance of the `schema`
        dataclass.

        Returns:
            C: Dataclass instance holding config
        """

        try:
            return parse_obj_as(self._schema, self._values)
        except ValidationError as exc:
            raise InvalidConfigError(
                "Something is wrong with the configuration file: \n"
            ) from exc

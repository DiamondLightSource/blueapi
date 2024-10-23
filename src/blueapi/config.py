import os
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import Any, Generic, Literal, TypeVar

import yaml
from bluesky_stomp.models import BasicAuthentication
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from blueapi.utils import BlueapiBaseModel, InvalidConfigError, format_errors

LogLevel = Literal["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

ENV_PREFIX = "BLUEAPI."


class SourceKind(str, Enum):
    PLAN_FUNCTIONS = "planFunctions"
    DEVICE_FUNCTIONS = "deviceFunctions"
    DODAL = "dodal"


class Source(BaseModel):
    kind: SourceKind
    module: Path | str


class StompConfig(BaseModel):
    """
    Config for connecting to stomp broker
    """

    host: str = "localhost"
    port: int = 61613
    auth: BasicAuthentication | None = None


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
    events: WorkerEventConfig = Field(default_factory=WorkerEventConfig)


class LoggingConfig(BlueapiBaseModel):
    level: LogLevel = "INFO"


class RestConfig(BlueapiBaseModel):
    host: str = "localhost"
    port: int = 8000
    protocol: str = "http"


class ScratchRepository(BlueapiBaseModel):
    name: str = "example"
    remote_url: str = "https://github.com/example/example.git"


class ScratchConfig(BlueapiBaseModel):
    root: Path = Path("/tmp/scratch/blueapi")
    repositories: list[ScratchRepository] = Field(default_factory=list)


class ApplicationConfig(BlueapiBaseModel):
    """
    Config for the worker application as a whole. Root of
    config tree.
    """

    stomp: StompConfig | None = None
    env: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    api: RestConfig = Field(default_factory=RestConfig)
    scratch: ScratchConfig | None = None

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


def _recursively_updated_map(
    old: dict[str, Any], new: Mapping[str, Any]
) -> dict[str, Any]:
    updated = old.copy()  # Create a copy to avoid mutating the original dictionary
    for key, value in new.items():
        if (
            key in updated
            and isinstance(updated[key], dict)
            and isinstance(value, dict)
        ):
            updated[key] = _recursively_updated_map(updated[key], value)
        elif value is not None:
            updated[key] = value
    return updated


class ConfigLoader(Generic[C]):
    """
    Small utility class for loading config from various sources.
    """

    def __init__(self, schema: type[C]) -> None:
        self._adapter = TypeAdapter(schema)
        self._values: dict[str, Any] = {}

    def use_values(self, values: Mapping[str, Any]) -> None:
        """
        Use all values provided in the config, override any defaults.
        """
        self._values = _recursively_updated_map(self._values, values)

    def use_values_from_yaml(self, path: Path) -> None:
        """
        Use values from a YAML/JSON file, overriding previous values.
        """
        with path.open("r") as stream:
            values = yaml.load(stream, yaml.Loader)
        self.use_values(values)

    def use_values_from_env(self) -> None:
        """
        Load values from environment variables with a given prefix.
        """

        env_values = {}
        for key, value in os.environ.items():
            if key.startswith(ENV_PREFIX) and value is not None:
                # Convert key to a config path-like structure
                config_key = key.removeprefix(ENV_PREFIX).lower()
                li: list[str] = config_key.split(".")
                local_value = env_values
                while len(li) > 1:
                    key = li.pop(0)
                    local_value = local_value.setdefault(key, {})
                local_value.setdefault(li[0], value)
        self.use_values(env_values)

    def load(self) -> C:
        """
        Finalize and load the config as an instance of the schema dataclass.
        """
        try:
            return self._adapter.validate_python(self._values)
        except ValidationError as exc:
            pretty_error_messages = format_errors(exc.errors())

            raise InvalidConfigError(
                f"""Something is wrong with the configuration file:
                    {pretty_error_messages}
                """
            ) from exc

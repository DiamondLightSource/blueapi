from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import Any, Generic, Literal, TypeVar

import yaml
from services.blueapi.base_model import BlueapiBaseModel

LogLevel = Literal["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class InvalidConfigError(Exception):
    def __init__(self, message="Configuration is invalid"):
        super().__init__(message)


class ImportedModuleKind(str, Enum):
    PLAN_FUNCTIONS = "planFunctions"
    DEVICE_FUNCTIONS = "deviceFunctions"
    DODAL = "dodal"


class ImportedModule(BaseModel):
    kind: ImportedModuleKind
    modulePath: Path | str


class WorkerEventConfig(BlueapiBaseModel):
    """
    Config for event broadcasting via the message bus
    """

    broadcast_status_events: bool = True


class EnvironmentConfig(BlueapiBaseModel):
    """
    Config for the RunEngine environment
    """

    sources: list[ImportedModule] = [
        ImportedModule(
            kind=ImportedModuleKind.DEVICE_FUNCTIONS,
            module="blueapi.startup.example_devices",
        ),
        ImportedModule(
            kind=ImportedModuleKind.PLAN_FUNCTIONS,
            module="blueapi.startup.example_plans",
        ),
        ImportedModule(
            kind=ImportedModuleKind.PLAN_FUNCTIONS, module="dls_bluesky_core.plans"
        ),
        ImportedModule(
            kind=ImportedModuleKind.PLAN_FUNCTIONS, module="dls_bluesky_core.stubs"
        ),
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

    env: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    api: RestConfig = Field(default_factory=RestConfig)
    scratch: ScratchConfig | None = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ApplicationConfig):
            return (
                (self.env == other.env)
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

import textwrap
from collections.abc import Mapping
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Any, Generic, Literal, TypeVar, cast

import requests
import yaml
from bluesky_stomp.models import BasicAuthentication
from pydantic import (
    BaseModel,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
)

from blueapi.utils import BlueapiBaseModel, InvalidConfigError

LogLevel = Literal["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

FORBIDDEN_OWN_REMOTE_URL = "https://github.com/DiamondLightSource/blueapi.git"


class SourceKind(str, Enum):
    PLAN_FUNCTIONS = "planFunctions"
    DEVICE_FUNCTIONS = "deviceFunctions"
    DODAL = "dodal"


class Source(BlueapiBaseModel):
    kind: SourceKind
    module: Path | str


class StompConfig(BlueapiBaseModel):
    """
    Config for connecting to stomp broker
    """

    enabled: bool = Field(
        description="True if blueapi should connect to stomp for asynchronous "
        "event publishing",
        default=False,
    )
    host: str = Field(description="STOMP broker host", default="localhost")
    port: int = Field(description="STOMP broker port", default=61613)
    auth: BasicAuthentication | None = Field(
        description="Auth information for communicating with STOMP broker, if required",
        default=None,
    )


class WorkerEventConfig(BlueapiBaseModel):
    """
    Config for event broadcasting via the message bus
    """

    broadcast_status_events: bool = True


class MetadataConfig(BlueapiBaseModel):
    instrument_session: str
    instrument: str


class EnvironmentConfig(BlueapiBaseModel):
    """
    Config for the RunEngine environment
    """

    sources: list[Source] = [
        Source(
            kind=SourceKind.DEVICE_FUNCTIONS, module="blueapi.startup.example_devices"
        ),
        Source(kind=SourceKind.PLAN_FUNCTIONS, module="blueapi.startup.example_plans"),
        Source(kind=SourceKind.PLAN_FUNCTIONS, module="dodal.plans"),
        Source(kind=SourceKind.PLAN_FUNCTIONS, module="dodal.plan_stubs.wrapped"),
    ]
    events: WorkerEventConfig = Field(default_factory=WorkerEventConfig)
    metadata: MetadataConfig | None = Field(default=None)


class GraylogConfig(BlueapiBaseModel):
    enabled: bool = False
    host: str = "localhost"
    port: int = 5555


class LoggingConfig(BlueapiBaseModel):
    level: LogLevel = "INFO"
    graylog: GraylogConfig = GraylogConfig()


class CORSConfig(BlueapiBaseModel):
    origins: list[str]
    allow_credentials: bool = False
    allow_methods: list[str] = ["*"]
    allow_headers: list[str] = ["*"]


class RestConfig(BlueapiBaseModel):
    host: str = "localhost"
    port: int = 8000
    protocol: str = "http"
    cors: CORSConfig | None = None


class ScratchRepository(BlueapiBaseModel):
    name: str = Field(
        description="Unique name for this repository in the scratch directory",
        default="example",
    )
    remote_url: str = Field(
        description="URL to clone from",
        default="https://github.com/example/example.git",
    )

    @field_validator("remote_url")
    @classmethod
    def check_remote_url(cls, value: str) -> str:
        if value == FORBIDDEN_OWN_REMOTE_URL:
            raise ValueError(f"remote_url '{value}' is not allowed.")
        return value


class ScratchConfig(BlueapiBaseModel):
    root: Path = Field(
        description="The root directory of the scratch area, all repositories will "
        "be cloned under this directory.",
        default=Path("/tmp/scratch/blueapi"),
    )
    required_gid: int | None = Field(
        description=textwrap.dedent("""
    Required owner GID for the scratch directory. If supplied the setup-scratch
    command will check the scratch area ownership and raise an error if it is
    not owned by <GID>.
    """),
        default=None,
    )
    repositories: list[ScratchRepository] = Field(
        description="Details of repositories to be cloned and imported into blueapi",
        default_factory=list,
    )


class OIDCConfig(BlueapiBaseModel):
    well_known_url: str = Field(
        description="URL to fetch OIDC config from the provider"
    )
    client_id: str = Field(description="Client ID")
    client_audience: str = Field(description="Client Audience(s)", default="blueapi")

    @cached_property
    def _config_from_oidc_url(self) -> dict[str, Any]:
        response: requests.Response = requests.get(self.well_known_url)
        response.raise_for_status()
        return response.json()

    @cached_property
    def device_authorization_endpoint(self) -> str:
        return cast(
            str, self._config_from_oidc_url.get("device_authorization_endpoint")
        )

    @cached_property
    def token_endpoint(self) -> str:
        return cast(str, self._config_from_oidc_url.get("token_endpoint"))

    @cached_property
    def issuer(self) -> str:
        return cast(str, self._config_from_oidc_url.get("issuer"))

    @cached_property
    def authorization_endpoint(self) -> str:
        return cast(str, self._config_from_oidc_url.get("authorization_endpoint"))

    @cached_property
    def jwks_uri(self) -> str:
        return cast(str, self._config_from_oidc_url.get("jwks_uri"))

    @cached_property
    def end_session_endpoint(self) -> str:
        return cast(str, self._config_from_oidc_url.get("end_session_endpoint"))

    @cached_property
    def id_token_signing_alg_values_supported(self) -> list[str]:
        return cast(
            list[str],
            self._config_from_oidc_url.get("id_token_signing_alg_values_supported"),
        )


class NumtrackerConfig(BlueapiBaseModel):
    url: str = "http://localhost:8002/graphql"


class ApplicationConfig(BlueapiBaseModel):
    """
    Config for the worker application as a whole. Root of
    config tree.
    """

    stomp: StompConfig = Field(default_factory=StompConfig)
    env: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    api: RestConfig = Field(default_factory=RestConfig)
    scratch: ScratchConfig | None = None
    oidc: OIDCConfig | None = None
    auth_token_path: Path | None = None
    numtracker: NumtrackerConfig | None = None

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

    def __init__(self, schema: type[C]) -> None:
        self._adapter = TypeAdapter(schema)
        self._values: dict[str, Any] = {}

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
            return self._adapter.validate_python(self._values)
        except ValidationError as exc:
            error_details = "\n".join(str(e) for e in exc.errors())
            raise InvalidConfigError(
                f"Something is wrong with the configuration file: \n {error_details}"
            ) from exc


class MissingStompConfiguration(Exception):
    pass

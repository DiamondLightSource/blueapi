import os
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import Any, Generic, Literal, TypeVar

import requests
import yaml
from bluesky_stomp.models import BasicAuthentication
from pydantic import (
    BaseModel,
    Field,
    Secret,
    TypeAdapter,
    ValidationError,
    field_validator,
)

from blueapi.utils import BlueapiBaseModel, InvalidConfigError

LogLevel = Literal["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


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


class OauthConfig(BlueapiBaseModel):
    oidc_config_url: str = Field(
        description="URL to fetch OIDC config from the provider"
    )
    # Initialized post-init
    device_auth_url: str
    pkce_auth_url: str
    token_url: str
    issuer: str
    jwks_uri: str
    logout_url: str
    refresh_url: str

    def model_post_init(self, __context: Any) -> None:
        response = requests.get(self.oidc_config_url)
        response.raise_for_status()
        config_data = response.json()

        self.device_auth_url = config_data.get("device_authorization_endpoint")
        self.pkce_auth_url = config_data.get("authorization_endpoint")
        self.token_url = config_data.get("token_endpoint")
        self.issuer = config_data.get("issuer")
        self.jwks_uri = config_data.get("jwks_uri")
        self.logout_url = config_data.get("end_session_endpoint")
        self.refresh_url = config_data.get("end_session_endpoint")
        # post this we need to check if all the values are present
        if not (
            self.device_auth_url
            and self.pkce_auth_url
            and self.token_url
            and self.issuer
            and self.jwks_uri
            and self.logout_url
        ):
            raise ValueError("OIDC config is missing required fields")


class SwaggerAuthConfig(BlueapiBaseModel):
    client_id: str = Field(description="Client ID for PKCE client")
    client_secret: Secret[str] = Field(
        description="Password to verify PKCE client's identity"
    )
    client_audience: str

    @field_validator("client_secret", mode="before")
    @classmethod
    def get_from_env(cls, v: str):
        if v.startswith("${") and v.endswith("}"):
            return os.environ[v.removeprefix("${").removesuffix("}").upper()]
        return v


class CLIAuthConfig(BlueapiBaseModel):
    client_id: str = Field(description="Client ID for CLI client")
    client_audience: str = Field(description="Audience for CLI client")
    token_file_path: str = "~/token"


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
    oauth: OauthConfig | None = None
    cliAuth: CLIAuthConfig | None = None
    swaggerAuth: SwaggerAuthConfig | None = None

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
            raise InvalidConfigError(
                "Something is wrong with the configuration file: \n"
            ) from exc

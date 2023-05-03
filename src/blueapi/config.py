from pathlib import Path
from typing import Optional, Union

import yaml
from pydantic import Field, ValidationError

from blueapi.utils import BlueapiBaseModel, InvalidConfigError

DEFAULT_YAML_PATH = Path("blueapi_config.yaml")


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


class ConfigLoader:
    """
    Small utility class for loading config from a yaml file.
    """

    source: Optional[Path]
    config: ApplicationConfig = ApplicationConfig()

    def __init__(self, source: Optional[Union[str, Path]] = DEFAULT_YAML_PATH) -> None:
        if source:
            self.source = Path(source) if isinstance(source, str) else source
        else:
            self.source = None

        self.load_from_yaml()

    def load_from_yaml(self) -> None:
        """
        Use all values provided in the YAML/JSON file in self.source.
        """
        if not self.source:
            return

        with self.source.open("r") as stream:
            values = yaml.safe_load(stream)

        try:
            self.config = ApplicationConfig(**values)
        except ValidationError as error:
            raise InvalidConfigError from error

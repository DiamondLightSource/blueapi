from pathlib import Path
from typing import Union

from pydantic import Field

from blueapi.utils import BlueapiBaseModel


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

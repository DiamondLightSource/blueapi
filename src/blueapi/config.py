from pathlib import Path
from typing import Union

from pydantic import BaseModel, Field


class StompConfig(BaseModel):
    """
    Config for connecting to stomp broker
    """

    host: str = "localhost"
    port: int = 61613


class EnvironmentConfig(BaseModel):
    """
    Config for the RunEngine environment
    """

    startup_script: Union[Path, str] = "blueapi.startup.example"


class LoggingConfig(BaseModel):
    level: str = "INFO"


class ApplicationConfig(BaseModel):
    """
    Config for the worker application as a whole. Root of
    config tree.
    """

    stomp: StompConfig = Field(default_factory=StompConfig)
    env: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

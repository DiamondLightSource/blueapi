from dataclasses import dataclass, field
from pathlib import Path
from typing import Union


@dataclass
class StompConfig:
    """
    Config for connecting to stomp broker
    """

    host: str = "localhost"
    port: int = 61613


@dataclass
class EnvironmentConfig:
    """
    Config for the RunEngine environment
    """

    startup_script: Union[Path, str] = "blueapi.startup.example"


@dataclass
class LoggingConfig:
    level: str = "INFO"


@dataclass
class ApplicationConfig:
    """
    Config for the worker application as a whole. Root of
    config tree.
    """

    stomp: StompConfig = field(default_factory=StompConfig)
    env: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

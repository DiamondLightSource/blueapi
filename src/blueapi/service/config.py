from dataclasses import dataclass, field
from pathlib import Path
from typing import Union


@dataclass
class StompConfig:
    host: str = "localhost"
    port: int = 61616


@dataclass
class EnvironmentConfig:
    startup_script: Union[Path, str] = "blueapi.service.example"


@dataclass
class ApplicationConfig:
    stomp: StompConfig = field(default_factory=StompConfig)
    env: EnvironmentConfig = field(default_factory=EnvironmentConfig)

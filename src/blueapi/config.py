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


@dataclass  # TODO: Defer immediately to pika.ConnectionProperties?
class AMQPConfig:
    """
    Config for connecting to the AMQP broker
    """
    host: str = "localhost"
    port: int = 5672
    userid: str = "guest"  # TODO: Config reads from env, so can be injected as Secret?
    password: str = "guest"  # Can only use guest/guest on loopback address
    virtual_host: str = "/"


@dataclass
class MessagingConfig:
    impl: str = 'stomp'
    stomp: StompConfig = field(default_factory=StompConfig)
    amqp: AMQPConfig = field(default_factory=AMQPConfig)


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

    messaging: MessagingConfig = field(default_factory=MessagingConfig)
    env: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

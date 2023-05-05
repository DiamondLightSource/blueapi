import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from blueapi.config import ApplicationConfig, AppSettings
from blueapi.core import BlueskyContext
from blueapi.messaging import StompMessagingTemplate
from blueapi.messaging.base import MessagingTemplate
from blueapi.utils import ConfigLoader
from blueapi.worker.reworker import RunEngineWorker
from blueapi.worker.worker import Worker

settings = AppSettings()


class Handler:
    context: BlueskyContext
    worker: Worker
    config: ApplicationConfig
    message_bus: MessagingTemplate

    def __init__(self, config_path: Optional[Path]) -> None:
        self.context = BlueskyContext()

        loader = ConfigLoader(ApplicationConfig)
        if config_path is not None:
            loader.use_yaml_or_json_file(config_path)
        self.config = loader.load()
        logging.basicConfig(level=self.config.logging.level)

        self.context.with_startup_script(self.config.env.startup_script)

        self.worker = RunEngineWorker(self.context)
        self.message_bus = StompMessagingTemplate.autoconfigured(self.config.stomp)

    def start(self) -> None:
        self.worker.start()

        self.worker.data_events.subscribe(
            lambda event, corr_id: self.message_bus.send(
                "public.worker.event.data", event, None, corr_id
            )
        )
        self.worker.progress_events.subscribe(
            lambda event, corr_id: self.message_bus.send(
                "public.worker.event.progress", event, None, corr_id
            )
        )

        self.message_bus.connect()

    def stop(self) -> None:
        self.worker.stop()
        self.message_bus.disconnect()


@lru_cache(maxsize=50)
def get_handler() -> Handler:
    """Retrieve the handler which wraps the bluesky context, worker and message bus."""
    config_path: Optional[Path] = (
        Path(settings.app_config_path) if settings.app_config_path is not None else None
    )

    handler = Handler(config_path)
    handler.start()
    return handler


def teardown_handler() -> None:
    """Stop all handler tasks. Does nothing if setup_handler has not been called."""
    handler = get_handler()
    handler.stop()

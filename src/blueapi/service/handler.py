import logging
from functools import lru_cache
from typing import Optional

from blueapi.config import ApplicationConfig, ConfigLoader
from blueapi.core import BlueskyContext
from blueapi.messaging import StompMessagingTemplate
from blueapi.messaging.base import MessagingTemplate
from blueapi.worker.reworker import RunEngineWorker
from blueapi.worker.worker import Worker


class Handler:
    context: BlueskyContext
    worker: Worker
    config: ApplicationConfig
    message_bus: MessagingTemplate

    def __init__(self, config: Optional[ApplicationConfig] = None) -> None:
        self.context = BlueskyContext()
        self.config = config if config is not None else ApplicationConfig()

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


HANDLER: Optional[Handler] = None


def setup_handler(
    config_loader: Optional[ConfigLoader[ApplicationConfig]] = None,
) -> None:
    global HANDLER
    handler = Handler(config_loader.load() if config_loader else None)
    handler.start()

    HANDLER = handler


def get_handler() -> Handler:
    """Retrieve the handler which wraps the bluesky context, worker and message bus."""
    if HANDLER is None:
        raise ValueError()
    return HANDLER


def teardown_handler() -> None:
    """Stop all handler tasks. Does nothing if setup_handler has not been called."""
    handler = get_handler()
    handler.stop()

import logging
from typing import Mapping, Optional

from blueapi.config import ApplicationConfig
from blueapi.core import BlueskyContext
from blueapi.core.event import EventStream
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

        self.context.with_config(self.config.env)

        self.worker = RunEngineWorker(self.context)
        self.message_bus = StompMessagingTemplate.autoconfigured(self.config.stomp)

    def start(self) -> None:
        self.worker.start()

        self._publish_event_streams(
            {
                self.worker.worker_events: self.message_bus.destinations.topic(
                    "public.worker.event"
                ),
                self.worker.progress_events: self.message_bus.destinations.topic(
                    "public.worker.event.progress"
                ),
                self.worker.data_events: self.message_bus.destinations.topic(
                    "public.worker.event.data"
                ),
            }
        )

        self.message_bus.connect()

    def _publish_event_streams(
        self, streams_to_destinations: Mapping[EventStream, str]
    ) -> None:
        for stream, destination in streams_to_destinations.items():
            self._publish_event_stream(stream, destination)

    def _publish_event_stream(self, stream: EventStream, destination: str) -> None:
        stream.subscribe(
            lambda event, correlation_id: self.message_bus.send(
                destination, event, None, correlation_id
            )
        )

    def stop(self) -> None:
        self.worker.stop()
        self.message_bus.disconnect()


HANDLER: Optional[Handler] = None


def setup_handler(
    config: Optional[ApplicationConfig] = None,
) -> None:
    global HANDLER
    handler = Handler(config)
    handler.start()

    HANDLER = handler


def get_handler() -> Handler:
    """Retrieve the handler which wraps the bluesky context, worker and message bus."""
    if HANDLER is None:
        raise ValueError()
    return HANDLER


def teardown_handler() -> None:
    """Stop all handler tasks. Does nothing if setup_handler has not been called."""
    global HANDLER
    if HANDLER is None:
        return
    handler = get_handler()
    handler.stop()
    HANDLER = None

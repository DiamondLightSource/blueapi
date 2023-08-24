import logging
from typing import Any, Mapping, Optional

from blueapi.config import ApplicationConfig
from blueapi.core import BlueskyContext
from blueapi.core.event import EventStream
from blueapi.messaging import StompMessagingTemplate
from blueapi.messaging.base import MessagingTemplate
from blueapi.worker.reworker import RunEngineWorker
from blueapi.worker.worker import Worker

LOGGER = logging.getLogger(__name__)


class BlueskyController:
    """
    Holder object for all objects required to manage and communicate
    with a run engine.
    """

    context: BlueskyContext
    worker: Worker
    config: ApplicationConfig
    messaging_template: Optional[MessagingTemplate]

    def __init__(
        self,
        context: BlueskyContext,
        worker: Worker,
        messaging_template: Optional[MessagingTemplate] = None,
    ) -> None:
        """Constructor

        Args:
            context: Context referring to plans and devices
            worker: Worker object that manages run engine
            messaging_template: Message handling object that can publish events
                from the worker. Defaults to None.
        """
        self.context = context
        self.worker = worker
        self.messaging_template = messaging_template

    @classmethod
    def from_config(cls, config: ApplicationConfig) -> "BlueskyController":
        context = BlueskyContext()
        context.with_config(config.env)
        worker = RunEngineWorker(context)
        if config.stomp is not None:
            messaging_template = StompMessagingTemplate.autoconfigured(config.stomp)
        else:
            messaging_template = None
        return cls(context, worker, messaging_template)

    def start(self) -> None:
        self.worker.start()

        if self.messaging_template is not None:
            topic = self.messaging_template.destinations.topic("public.worker.event")
            self._publish_event_streams(
                {
                    self.worker.worker_events: topic,
                    self.worker.progress_events: topic,
                    self.worker.data_events: topic,
                }
            )

            self.messaging_template.connect()

    def _publish_event_streams(
        self, streams_to_destinations: Mapping[EventStream, str]
    ) -> None:
        for stream, destination in streams_to_destinations.items():
            self._publish_event_stream(stream, destination)

    def _publish_event_stream(self, stream: EventStream, destination: str) -> None:
        def on_event(event: Any, correlation_id: Optional[str]) -> None:
            if self.messaging_template is not None:
                self.messaging_template.send(
                    destination,
                    event,
                    None,
                    correlation_id,
                )

        stream.subscribe(on_event)

    def stop(self) -> None:
        self.worker.stop()
        if self.messaging_template is not None:
            self.messaging_template.disconnect()


_CONTROLLER: Optional[BlueskyController] = None


def initialize_controller(config: ApplicationConfig) -> None:
    global _CONTROLLER
    _CONTROLLER = BlueskyController.from_config(config)
    _CONTROLLER.start()


def get_controller() -> BlueskyController:
    """Retrieve the handler which wraps the bluesky context, worker and message bus."""
    if _CONTROLLER is None:
        raise ValueError("Controller not initialized")
    return _CONTROLLER


def teardown_controller() -> None:
    """Stop all handler tasks. Does nothing if setup_handler has not been called."""
    global _CONTROLLER
    if _CONTROLLER is not None:
        _CONTROLLER.stop()
        _CONTROLLER = None

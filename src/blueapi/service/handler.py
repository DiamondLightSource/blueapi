import logging
from functools import partial
from typing import Mapping, Optional

from dodal.parameters.gda_directory_provider import (
    VisitDirectoryProvider,
    VisitDirectoryProviderConfig,
)

from blueapi.config import ApplicationConfig
from blueapi.core import BlueskyContext
from blueapi.core.event import EventStream
from blueapi.messaging import StompMessagingTemplate
from blueapi.messaging.base import MessagingTemplate
from blueapi.preprocessors.attach_metadata import attach_metadata
from blueapi.worker.reworker import RunEngineWorker
from blueapi.worker.worker import Worker

LOGGER = logging.getLogger(__name__)


class Handler:
    context: BlueskyContext
    worker: Worker
    config: ApplicationConfig
    messaging_template: MessagingTemplate

    def __init__(
        self,
        config: Optional[ApplicationConfig] = None,
        context: Optional[BlueskyContext] = None,
        messaging_template: Optional[MessagingTemplate] = None,
        worker: Optional[Worker] = None,
    ) -> None:
        self.config = config or ApplicationConfig()
        self.context = context or BlueskyContext()

        self.context.with_config(self.config.env)

        self.worker = worker or RunEngineWorker(self.context)
        self.messaging_template = (
            messaging_template
            or StompMessagingTemplate.autoconfigured(self.config.stomp)
        )

    def start(self) -> None:
        self.worker.start()

        self._publish_event_streams(
            {
                self.worker.worker_events: self.messaging_template.destinations.topic(
                    "public.worker.event"
                ),
                self.worker.progress_events: self.messaging_template.destinations.topic(
                    "public.worker.event"
                ),
                self.worker.data_events: self.messaging_template.destinations.topic(
                    "public.worker.event"
                ),
            }
        )

        self.messaging_template.connect()

    def _publish_event_streams(
        self, streams_to_destinations: Mapping[EventStream, str]
    ) -> None:
        for stream, destination in streams_to_destinations.items():
            self._publish_event_stream(stream, destination)

    def _publish_event_stream(self, stream: EventStream, destination: str) -> None:
        stream.subscribe(
            lambda event, correlation_id: self.messaging_template.send(
                destination, event, None, correlation_id
            )
        )

    def stop(self) -> None:
        self.worker.stop()
        self.messaging_template.disconnect()


HANDLER: Optional[Handler] = None


def setup_handler(
    config: Optional[ApplicationConfig] = None,
) -> None:
    global HANDLER

    provider = None
    plan_wrappers = []

    if config:
        data_groups = [
            config.env.facility,
            config.env.science_group,
            config.env.beamline,
            config.env.visit_id,
        ]
        provider = VisitDirectoryProvider(
            VisitDirectoryProviderConfig(
                url=config.env.visit_service_url,
                beamline=config.env.beamline,
                base_path=config.env.visit_id,
            )
        )

        # Make all dodal devices created by the context use provider if they can
        from dodal.parameters.gda_directory_provider import (
            set_directory_provider_singleton,
        )

        set_directory_provider_singleton(provider)

        attach_metadata_with_config = partial(attach_metadata, data_groups, provider)
        plan_wrappers.append(attach_metadata_with_config)

    handler = Handler(
        config,
        context=BlueskyContext(
            plan_wrappers=plan_wrappers, directory_provider=provider
        ),
    )
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

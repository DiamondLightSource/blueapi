import logging
from typing import Mapping, Optional

from blueapi.config import ApplicationConfig
from blueapi.core import (
    BlueskyContext,
    PlanPreprocessor,
    PreprocessorApplicationPolicy,
    PreprocessorModel,
)
from blueapi.core.event import EventStream
from blueapi.data_management.gda_directory_provider import (
    LocalVisitServiceClient,
    VisitDirectoryProvider,
    VisitServiceClient,
    VisitServiceClientBase,
)
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

    if config is not None:
        visit_service_client: VisitServiceClientBase
        if config.env.data_writing.visit_service_url is not None:
            visit_service_client = VisitServiceClient(
                config.env.data_writing.visit_service_url
            )
        else:
            visit_service_client = LocalVisitServiceClient()

        provider = VisitDirectoryProvider(
            data_group_name=config.env.data_writing.group_name,
            data_directory=config.env.data_writing.visit_directory,
            client=visit_service_client,
        )

        # Make all dodal devices created by the context use provider if they can
        try:
            from dodal.parameters.gda_directory_provider import (
                set_directory_provider_singleton,
            )

            set_directory_provider_singleton(provider)
        except ImportError:
            logging.error(
                "Unable to set directory provider for ophyd-async devices, "
                "a newer version of dodal is required"
            )

        plan_wrappers = {
            "data_writing_metadata": PlanPreprocessor(
                PreprocessorModel(
                    name="data_writing_metadata",
                    description="""
                    When a plan collects data, this preprocessor will cause
                    ophyd-async detectors to write to a specified directory
                    (unique per collection).
                    It will also bundle grouping information about these
                    detectors into the run start document.
                    """,
                    application_policy=PreprocessorApplicationPolicy.ALWAYS,
                ),
                lambda plan: attach_metadata(plan, provider),
            )
        }
    else:
        plan_wrappers = {}
        provider = None

    handler = Handler(
        config,
        context=BlueskyContext(
            plan_wrappers=plan_wrappers,
            directory_provider=provider,
            sim=False,
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

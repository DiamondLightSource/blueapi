import logging
from collections.abc import Mapping
from typing import Any

from blueapi.config import ApplicationConfig
from blueapi.core import BlueskyContext
from blueapi.core.event import EventStream
from blueapi.messaging import StompMessagingTemplate
from blueapi.messaging.base import MessagingTemplate
from blueapi.service.handler_base import BlueskyHandler
from blueapi.service.model import DeviceModel, PlanModel, WorkerTask
from blueapi.worker.event import WorkerState
from blueapi.worker.reworker import TaskWorker
from blueapi.worker.task import Task
from blueapi.worker.worker import TrackableTask, Worker

LOGGER = logging.getLogger(__name__)


class Handler(BlueskyHandler):
    _context: BlueskyContext
    _worker: Worker
    _config: ApplicationConfig
    _messaging_template: MessagingTemplate | None
    _initialized: bool = False

    def __init__(
        self,
        config: ApplicationConfig | None = None,
        context: BlueskyContext | None = None,
        messaging_template: MessagingTemplate | None = None,
        worker: Worker | None = None,
    ) -> None:
        self._config = config or ApplicationConfig()
        self._context = context or BlueskyContext()

        self._context.with_config(self._config.env)

        self._worker = worker or TaskWorker(
            self._context,
            broadcast_statuses=self._config.env.events.broadcast_status_events,
        )
        if self._config.stomp is None:
            self._messaging_template = messaging_template
        else:
            self._messaging_template = (
                messaging_template
                or StompMessagingTemplate.autoconfigured(self._config.stomp)
            )

    def start(self) -> None:
        self._worker.start()

        if self._messaging_template is not None:
            event_topic = self._messaging_template.destinations.topic(
                "public.worker.event"
            )
            self._publish_event_streams(
                {
                    self._worker.worker_events: event_topic,
                    self._worker.progress_events: event_topic,
                    self._worker.data_events: event_topic,
                }
            )

            self._messaging_template.connect()
        self._initialized = True

    def _publish_event_streams(
        self, streams_to_destinations: Mapping[EventStream, str]
    ) -> None:
        for stream, destination in streams_to_destinations.items():
            self._publish_event_stream(stream, destination)

    def _publish_event_stream(self, stream: EventStream, destination: str) -> None:
        def forward_message(event: Any, correlation_id: str | None) -> None:
            if self._messaging_template is not None:
                self._messaging_template.send(destination, event, None, correlation_id)

        stream.subscribe(forward_message)

    def stop(self) -> None:
        self._initialized = False
        self._worker.stop()
        if (
            self._messaging_template is not None
            and self._messaging_template.is_connected()
        ):
            self._messaging_template.disconnect()

    @property
    def plans(self) -> list[PlanModel]:
        return [PlanModel.from_plan(plan) for plan in self._context.plans.values()]

    def get_plan(self, name: str) -> PlanModel:
        return PlanModel.from_plan(self._context.plans[name])

    @property
    def devices(self) -> list[DeviceModel]:
        return [
            DeviceModel.from_device(device) for device in self._context.devices.values()
        ]

    def get_device(self, name: str) -> DeviceModel:
        return DeviceModel.from_device(self._context.devices[name])

    def submit_task(self, task: Task) -> str:
        return self._worker.submit_task(task)

    def clear_task(self, task_id: str) -> str:
        return self._worker.clear_task(task_id)

    def begin_task(self, task: WorkerTask) -> WorkerTask:
        if task.task_id is not None:
            self._worker.begin_task(task.task_id)
        return task

    @property
    def active_task(self) -> TrackableTask | None:
        return self._worker.get_active_task()

    @property
    def state(self) -> WorkerState:
        return self._worker.state

    def pause_worker(self, defer: bool | None) -> None:
        self._worker.pause(defer)

    def resume_worker(self) -> None:
        self._worker.resume()

    def cancel_active_task(self, failure: bool, reason: str | None):
        self._worker.cancel_active_task(failure, reason)

    @property
    def tasks(self) -> list[TrackableTask]:
        return self._worker.get_tasks()

    def get_task_by_id(self, task_id: str) -> TrackableTask | None:
        return self._worker.get_task_by_id(task_id)

    @property
    def initialized(self) -> bool:
        return self._initialized


HANDLER: Handler | None = None


def setup_handler(
    config: ApplicationConfig | None = None,
) -> None:
    global HANDLER

    handler = Handler(
        config,
        context=BlueskyContext(),
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

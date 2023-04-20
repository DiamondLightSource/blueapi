import logging
import uuid
from typing import Mapping

from fastapi import FastAPI

from blueapi.config import ApplicationConfig
from blueapi.core import BlueskyContext, EventStream
from blueapi.messaging import MessageContext, MessagingTemplate, StompMessagingTemplate
from blueapi.worker import RunEngineWorker, RunPlan, Worker
from blueapi import context, worker
from blueapi.worker.multithread import run_worker_in_own_thread

from .routes import router

from .model import (
    DeviceModel,
    DeviceRequest,
    DeviceResponse,
    PlanModel,
    PlanRequest,
    PlanResponse,
    TaskResponse,
)


class Service:
    _config: ApplicationConfig
    _ctx: BlueskyContext
    _worker: Worker
    _template: MessagingTemplate

    def __init__(self, config: ApplicationConfig) -> None:
        self._config = config
        self._ctx = BlueskyContext()
        self._ctx.with_startup_script(self._config.env.startup_script)
        self._worker = RunEngineWorker(self._ctx)
        self._template = StompMessagingTemplate.autoconfigured(config.stomp)

    def run(self) -> None:
        logging.basicConfig(level=self._config.logging.level)

        self._publish_event_streams(
            {
                self._worker.worker_events: self._template.destinations.topic(
                    "public.worker.event"
                ),
                self._worker.progress_events: self._template.destinations.topic(
                    "public.worker.event.progress"
                ),
                self._worker.data_events: self._template.destinations.topic(
                    "public.worker.event.data"
                ),
            }
        )

        self._template.subscribe(" ", self._on_run_request)
        self._template.subscribe("worker.plans", self._get_plans)
        self._template.subscribe("worker.devices", self._get_devices)

        self._template.connect()

        self._worker.run()

    def _publish_event_streams(
        self, streams_to_destinations: Mapping[EventStream, str]
    ) -> None:
        for stream, destination in streams_to_destinations.items():
            self._publish_event_stream(stream, destination)

    def _publish_event_stream(self, stream: EventStream, destination: str) -> None:
        stream.subscribe(
            lambda event, correlation_id: self._template.send(
                destination, event, None, correlation_id
            )
        )

    def _on_run_request(self, message_context: MessageContext, task: RunPlan) -> None:
        correlation_id = message_context.correlation_id or str(uuid.uuid1())
        self._worker.submit_task(correlation_id, task)

        reply_queue = message_context.reply_destination
        if reply_queue is not None:
            response = TaskResponse(task_name=correlation_id)
            self._template.send(reply_queue, response)

    def _get_plans(self, message_context: MessageContext, message: PlanRequest) -> None:
        plans = list(map(PlanModel.from_plan, self._ctx.plans.values()))
        response = PlanResponse(plans=plans)

        assert message_context.reply_destination is not None
        self._template.send(message_context.reply_destination, response)

    def _get_devices(
        self, message_context: MessageContext, message: DeviceRequest
    ) -> None:
        devices = list(map(DeviceModel.from_device, self._ctx.devices.values()))
        response = DeviceResponse(devices=devices)

        assert message_context.reply_destination is not None
        self._template.send(message_context.reply_destination, response)


##need to globally, start the worker and message bus.
## message bus needs a config file,
## worker needs a context,
## context needs a config file.

## so how about, we set up a context somewhere (in context module),
## we start up the worker with the context,
# THEN in this start we load config into the context and load the message bus from the config.

## the rest api never needs to interact with the message bus anyways... it only interacts with context or worker.


def start(config_path: Optional[Path] = None):
    # 1. load config and setup logging
    loader = ConfigLoader(ApplicationConfig)
    if config_path is not None:
        loader.use_yaml_or_json_file(config_path)
    config = loader.load()
    logging.basicConfig(level=config.logging.level)

    # 2. set context with startup script
    context.with_startup_script(config.env.startup_script)

    # 3. run the worker in it's own thread
    worker_future = run_worker_in_own_thread(worker)

    # 4. create a message bus and subscribe all relevant worker docs to it
    message_bus = StompMessagingTemplate.autoconfigured(config.stomp)
    worker.data_events.subscribe(
        lambda event, corr_id: message_bus.send(
            "public.worker.event.data", event, None, corr_id
        )
    )
    worker.progress_events.subscribe(
        lambda event, corr_id: message_bus.send(
            "public.worker.event.progress", event, None, corr_id
        )
    )

    # 5. start the message bus
    message_bus.connect()

    # 7. run the worker forever
    worker.run_forever()

    # Service(config).run()

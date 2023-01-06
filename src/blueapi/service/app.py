import logging
import uuid
from pathlib import Path
from typing import Optional

from blueapi.config import ApplicationConfig
from blueapi.core import BlueskyContext, DataEvent
from blueapi.messaging import MessageContext, MessagingTemplate, StompMessagingTemplate
from blueapi.utils import ConfigLoader
from blueapi.worker import RunEngineWorker, RunPlan, TaskEvent, Worker, WorkerEvent

from .model import (
    DeviceModel,
    DeviceRequest,
    DeviceResponse,
    PlanModel,
    PlanRequest,
    PlanResponse,
)

logging.basicConfig(level=logging.INFO)


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
        self._worker.worker_events.subscribe(self._on_worker_event)
        self._worker.task_events.subscribe(self._on_task_event)
        self._worker.data_events.subscribe(self._on_data_event)

        self._template.connect()

        self._template.subscribe("worker.run", self._on_run_request)
        self._template.subscribe("worker.plans", self._get_plans)
        self._template.subscribe("worker.devices", self._get_devices)

        self._worker.run_forever()

    def _on_worker_event(self, event: WorkerEvent) -> None:
        self._template.send(self._template.destinations.topic("worker.event"), event)

    def _on_task_event(self, event: TaskEvent) -> None:
        self._template.send(
            self._template.destinations.topic("worker.event.task"), event
        )

    def _on_data_event(self, event: DataEvent) -> None:
        self._template.send(
            self._template.destinations.topic("worker.event.data"), event
        )

    def _on_run_request(self, message_context: MessageContext, task: RunPlan) -> None:
        name = str(uuid.uuid1())
        self._worker.submit_task(name, task)

        reply_queue = message_context.reply_destination
        if reply_queue is not None:
            self._template.send(reply_queue, name)

    def _get_plans(self, message_context: MessageContext, message: PlanRequest) -> None:
        plans = list(map(PlanModel.from_plan, self._ctx.plans.values()))
        response = PlanResponse(plans)

        assert message_context.reply_destination is not None
        self._template.send(message_context.reply_destination, response)

    def _get_devices(
        self, message_context: MessageContext, message: DeviceRequest
    ) -> None:
        devices = list(map(DeviceModel.from_device, self._ctx.devices.values()))
        response = DeviceResponse(devices)

        assert message_context.reply_destination is not None
        self._template.send(message_context.reply_destination, response)


def start(config_path: Optional[Path] = None):
    loader = ConfigLoader(ApplicationConfig)
    if config_path is not None:
        loader.use_yaml_or_json_file(config_path)
    config = loader.load()

    Service(config).run()

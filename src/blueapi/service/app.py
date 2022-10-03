import logging
import uuid
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml

from blueapi.core import BlueskyContext, DataEvent
from blueapi.messaging import MessageContext, MessagingTemplate, StompMessagingTemplate
from blueapi.worker import RunEngineWorker, RunPlan, TaskEvent, Worker, WorkerEvent

from .config import ApplicationConfig
from .model import DeviceModel, PlanModel

ctx = BlueskyContext()


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
        self._template = StompMessagingTemplate.autoconfigured("127.0.0.1", 61613)

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

        assert message_context.reply_destination is not None
        self._template.send(message_context.reply_destination, name)

    def _get_plans(self, message_context: MessageContext, message: str) -> None:
        plans = list(map(PlanModel.from_plan, ctx.plans.values()))
        assert message_context.reply_destination is not None
        self._template.send(message_context.reply_destination, plans)

    def _get_devices(self, message_context: MessageContext, message: str) -> None:
        devices = list(map(DeviceModel.from_device, ctx.devices.values()))
        assert message_context.reply_destination is not None
        self._template.send(message_context.reply_destination, devices)


def _load_yaml_config(path: Path) -> Mapping[str, Any]:
    with path.open("r") as stream:
        return yaml.load(stream, yaml.Loader)


def start(config_path: Optional[Path] = None):
    if config_path is not None:
        overrides = _load_yaml_config(config_path)
    else:
        overrides = {}
    config = ApplicationConfig.load(overrides)

    Service(config).run()

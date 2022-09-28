import logging
import uuid

from ophyd.sim import Syn2DGauss

import blueapi.plans as default_plans
from blueapi.core import BlueskyContext, DataEvent
from blueapi.messaging import MessageContext, MessagingTemplate, StompMessagingTemplate
from blueapi.worker import RunEngineWorker, RunPlan, TaskEvent, Worker, WorkerEvent

from .model import DeviceModel, PlanModel
from .simmotor import SynAxisWithMotionEvents

ctx = BlueskyContext()
logging.basicConfig(level=logging.INFO)

ctx.plan_module(default_plans)
x = SynAxisWithMotionEvents(name="x", delay=1.0, events_per_move=8)
y = SynAxisWithMotionEvents(name="y", delay=3.0, events_per_move=24)
det = Syn2DGauss(
    name="det",
    motor0=x,
    motor_field0="x",
    motor1=y,
    motor_field1="y",
    center=(0, 0),
    Imax=1,
    labels={"detectors"},
)

ctx.device(x)
ctx.device(y)
ctx.device(det)


class Service:
    _worker: Worker
    _template: MessagingTemplate

    def __init__(self) -> None:
        self._worker = RunEngineWorker(ctx)
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
        # plans = list(map(PlanModel.from_plan, ctx.plans.values()))
        plans = list(ctx.plans.values())
        assert message_context.reply_destination is not None
        self._template.send(message_context.reply_destination, plans)

    def _get_devices(self, message_context: MessageContext, message: str) -> None:
        devices = list(map(DeviceModel.from_device, ctx.devices.values()))
        assert message_context.reply_destination is not None
        self._template.send(message_context.reply_destination, devices)


def main():
    Service().run()

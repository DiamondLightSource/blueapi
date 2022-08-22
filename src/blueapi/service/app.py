import logging
import uuid
from typing import Any, Iterable, Mapping

from bluesky.protocols import Flyable, Readable
from ophyd.sim import Syn2DGauss

import blueapi.plans as default_plans
from blueapi.core import BLUESKY_PROTOCOLS, BlueskyContext, DataEvent, Device, Plan
from blueapi.messaging import MessageContext, StompMessagingTemplate
from blueapi.worker import RunEngineWorker, RunPlan, TaskEvent, WorkerEvent

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


with StompMessagingTemplate.autoconfigured("127.0.0.1", 61613) as template:

    def _on_worker_event(event: WorkerEvent) -> None:
        template.send("worker.event", event)

    def _on_task_event(event: TaskEvent) -> None:
        template.send("worker.event.task", event)

    def _on_data_event(event: DataEvent) -> None:
        template.send("worker.event.data", event)

    worker = RunEngineWorker(ctx)

    worker.worker_events.subscribe(_on_worker_event)
    worker.task_events.subscribe(_on_task_event)
    worker.data_events.subscribe(_on_data_event)

    def _display_plan(plan: Plan) -> Mapping[str, Any]:
        return {"name": plan.name}

    def _display_device(device: Device) -> Mapping[str, Any]:
        if isinstance(device, Readable) or isinstance(device, Flyable):
            name = device.name
        else:
            name = "UNKNOWN"
        return {
            "name": name,
            "protocols": list(_protocol_names(device)),
        }

    def _protocol_names(device: Device) -> Iterable[str]:
        for protocol in BLUESKY_PROTOCOLS:
            if isinstance(device, protocol):
                yield protocol.__name__

    @template.listener(destination="worker.run")
    def on_run_request(message_context: MessageContext, task: RunPlan) -> None:
        name = str(uuid.uuid1())
        worker.submit_task(name, task)

        assert message_context.reply_destination is not None
        template.send(message_context.reply_destination, name)

    @template.listener("worker.plans")
    def get_plans(message_context: MessageContext, message: str) -> None:
        plans = list(map(_display_plan, ctx.plans.values()))
        assert message_context.reply_destination is not None
        template.send(message_context.reply_destination, plans)

    @template.listener("worker.devices")
    def get_devices(message_context: MessageContext, message: str) -> None:
        devices = list(map(_display_device, ctx.devices.values()))
        assert message_context.reply_destination is not None
        template.send(message_context.reply_destination, devices)

    def main():
        template.connect()
        worker.run_forever()

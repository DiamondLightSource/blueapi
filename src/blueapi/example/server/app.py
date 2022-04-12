import asyncio
import itertools
import logging

# worker.run_forever()
import time
import uuid
from dataclasses import dataclass
from typing import Any, Iterable, List, Mapping

import bluesky.plan_stubs as bps
import stomp
from apischema import deserialize
from apischema.json_schema import deserialization_schema
from bluesky.protocols import Flyable, Movable, Readable
from ophyd.sim import Syn2DGauss, SynAxis
from requests import request
from yaml import serialize

from blueapi.core import BLUESKY_PROTOCOLS, Ability, BlueskyContext, Plan
from blueapi.worker import (
    RunEngineWorker,
    RunPlan,
    WorkerEvent,
    run_worker_in_own_thread,
)

from ..messaging_app import MessageContext, MessagingApp

ctx = BlueskyContext()
logging.basicConfig(level=logging.INFO)


@ctx.plan
def sleep(time: float):
    yield from bps.sleep(5)


# @ctx.plan
# def move(positions: Mapping[Movable, Any]):
#     yield from bps.mv(*itertools.chain.from_iterable(positions.items()))


x = SynAxis(name="x", delay=0.1)
y = SynAxis(name="y", delay=0.1)
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

ctx.ability(x)
ctx.ability(y)
ctx.ability(det)


worker = RunEngineWorker(ctx)


app = MessagingApp("127.0.0.1", 61613)
app.connect()


def _on_worker_event(event: WorkerEvent) -> None:
    print(event)
    app.send("worker.event", event)


worker.subscribe(_on_worker_event)


def on_run_request(_: MessageContext, task: RunPlan) -> None:
    worker.submit_task(task)


app.subscribe(on_run_request, destination="worker.run", obj_type=RunPlan)


def get_plans(message_context: MessageContext, message: str) -> None:
    plans = list(map(_display_plan, ctx.plans.values()))
    message_context.reply(plans)


app.subscribe(get_plans, destination="worker.plans")


def _display_plan(plan: Plan) -> Mapping[str, Any]:
    return {"name": plan.name, "schema": deserialization_schema(plan.model)}


def _display_ability(ability: Ability) -> Mapping[str, Any]:
    if isinstance(ability, Readable) or isinstance(ability, Flyable):
        name = ability.name
    else:
        name = "UNKNOWN"
    return {
        "name": name,
        "protocols": list(_protocol_names(ability)),
    }


def _protocol_names(ability: Ability) -> Iterable[str]:
    for protocol in BLUESKY_PROTOCOLS:
        if isinstance(ability, protocol):
            yield protocol.__name__


worker.run_forever()

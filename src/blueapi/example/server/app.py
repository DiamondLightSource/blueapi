import asyncio
import itertools
import logging
import uuid
from typing import Any, Iterable, List, Mapping

import bluesky.plan_stubs as bps
from apischema.json_schema import deserialization_schema
from bluesky.protocols import Flyable, Movable, Readable
from fastapi import FastAPI, Request
from ophyd.sim import Syn2DGauss, SynAxis

import blueapi.plans
from blueapi.core import (
    BLUESKY_PROTOCOLS,
    Ability,
    BlueskyContext,
    BlueskyController,
    Plan,
)

ctx = BlueskyContext()
logging.basicConfig(level=logging.INFO)

ctx.plan_module(blueapi.plans)

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

controller = BlueskyController(ctx)


app = FastAPI()


@app.on_event("startup")
async def app_startup():
    asyncio.create_task(controller.run_workers())


@app.get("/plan")
async def get_plans() -> List[Mapping[str, Any]]:
    return list(map(_display_plan, controller.plans.values()))


@app.get("/plan/{name}")
async def get_plan(name: str) -> Mapping[str, Any]:
    return _display_plan(controller.plans[name])


def _display_plan(plan: Plan) -> Mapping[str, Any]:
    return {"name": plan.name, "schema": deserialization_schema(plan.model)}


@app.get("/ability")
async def get_abilities() -> List[Mapping[str, Any]]:
    return list(map(_display_ability, controller.abilities.values()))


@app.get("/ability/{name}")
async def get_ability(name: str) -> Mapping[str, Any]:
    return _display_ability(controller.abilities[name])


@app.put("/plan/{name}/run")
async def run_plan(request: Request, name: str) -> uuid.UUID:
    await controller.run_plan(name, await request.json())
    return uuid.uuid1()


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

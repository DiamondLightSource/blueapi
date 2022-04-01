import itertools
import logging
import re
import uuid
from typing import Any, List, Mapping, Optional

import bluesky.plan_stubs as bps
import bluesky.plans as bp
from apischema.json_schema import deserialization_schema
from bluesky.protocols import Movable, Readable
from fastapi import FastAPI

from blueapi.core import BlueskyContext, BlueskyController, Plan
from blueapi.core.bluesky_types import Ability

ctx = BlueskyContext()
logging.basicConfig(level=logging.INFO)


@ctx.plan
def sleep(time: float):
    yield from bps.sleep(5)


@ctx.plan
def move(positions: Mapping[Movable, Any]):
    yield from bps.mv(*itertools.chain.from_iterable(positions.items()))


@ctx.plan
def count_all_matching(match_str: str, metadata: Optional[Mapping[str, Any]] = None):
    matcher = re.compile(match_str)
    matching = filter(lambda ability: matcher.match(ability.name), abilities.visit())
    metadata = metadata or {}

    yield from bp.count(
        list(matching), md={**metadata, **{"matching_regex": match_str}}
    )


controller = BlueskyController(ctx)


app = FastAPI()


@app.on_event("startup")
async def app_startup():
    await controller.run_workers()


@app.get("/plans")
async def get_plans() -> List[Mapping[str, Any]]:
    def display_plan(plan: Plan) -> Mapping[str, Any]:
        return {"name": plan.name, "schema": deserialization_schema(plan.model)}

    return list(map(display_plan, await controller.get_plans()))


@app.get("/abilities")
async def get_abilities() -> List[Ability]:
    return list((await controller.get_abilities()).values())


@app.put("/plans/{name}/run")
async def run_plan(name: str, params: Mapping[str, Any]) -> uuid.UUID:
    await controller.run_plan(name, params)
    return uuid.uuid1()

import asyncio
import logging
import uuid
from typing import Any, List, Mapping

import bluesky.plan_stubs as bps
from apischema.json_schema import deserialization_schema
from fastapi import FastAPI, Request

from blueapi.core import BlueskyContext, BlueskyController, Plan

ctx = BlueskyContext()
logging.basicConfig(level=logging.INFO)


@ctx.plan
def sleep(time: float):
    yield from bps.sleep(5)


@ctx.plan
def move(motor: str, pos: float):
    yield from bps.mv(motor, pos)


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


@app.put("/plan/{name}/run")
async def run_plan(request: Request, name: str) -> uuid.UUID:
    await controller.run_plan(name, await request.json())
    return uuid.uuid1()

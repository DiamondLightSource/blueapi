from typing import Any, List, Mapping

import bluesky.plan_stubs as bps
from apischema.json_schema import deserialization_schema
from fastapi import FastAPI

from blueapi.core import BlueskyContext, BlueskyController, Plan

ctx = BlueskyContext()


@ctx.plan
def sleep(time: float):
    yield from bps.sleep(5)


@ctx.plan
def move(motor: str, pos: float):
    yield from bps.mv(motor, pos)


controller = BlueskyController(ctx)


app = FastAPI()


@app.get("/plans")
async def get_plans() -> List[Mapping[str, Any]]:
    def display_plan(plan: Plan) -> Mapping[str, Any]:
        return {"name": plan.name, "schema": deserialization_schema(plan.model)}

    return list(map(display_plan, await controller.get_plans()))

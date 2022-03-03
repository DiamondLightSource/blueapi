import asyncio
from abc import ABC, abstractmethod
from ast import Call
from ctypes import Union
from dataclasses import dataclass, field
from tkinter.messagebox import NO
from tokenize import Single
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    Mapping,
    Optional,
    Protocol,
    Type,
    TypeVar,
    runtime_checkable,
)

import aiohttp
from aiohttp import web
from bluesky.utils import Msg

from .params import schema_for_func

PlanGenerator = Callable[..., Generator[Msg, Any, None]]


@dataclass
class Plan:
    name: str
    model: Type[Any]
    func: PlanGenerator


class BlueskyAppBase(ABC):
    @abstractmethod
    def plan(self, plan: Plan):
        ...

    @abstractmethod
    def run(self) -> None:
        ...

    @abstractmethod
    async def run_async(self) -> None:
        ...


@dataclass
class BlueskyContext:
    plans: Dict[str, Plan] = field(default_factory=dict)


class BlueskyApp:
    _context: BlueskyContext

    def __init__(self, context: Optional[BlueskyContext] = None) -> None:
        self._context = context or BlueskyContext()

    def plan(self, plan: PlanGenerator) -> PlanGenerator:
        schema = schema_for_func(plan)
        self._context.plans[plan.__name__] = Plan(plan.__name__, schema, plan)
        return plan

    def run(self) -> None:
        asyncio.run(self.run_async())

    async def run_async(self) -> None:
        await setup_app(self._context)
        await asyncio.wait(asyncio.all_tasks())


async def setup_app(ctx: BlueskyContext) -> None:
    routes = web.RouteTableDef()

    @routes.put("/plans/{name}/run")
    async def handle_plan_request(request: web.Request) -> web.Response:
        plan_name = request.match_info["name"]
        params = await request.json()
        return web.json_response({"plan": plan_name, "params": params})

    @routes.get("/plans")
    async def get_plans(request: web.Request) -> web.Response:
        return web.json_response(
            {plan.name: {"model": "TBD"} for plan in ctx.plans.values()}
        )

    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print(f"running {site}")

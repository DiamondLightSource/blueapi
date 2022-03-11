import asyncio
import imp
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
from apischema.metadata import skip
from bluesky.utils import Msg

from .params import schema_for_func

PlanGenerator = Callable[..., Generator[Msg, Any, None]]


@dataclass
class Plan:
    name: str
    model: Type[Any]
    func: PlanGenerator = field(metadata=skip)


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


class BlueskyService(ABC):
    @abstractmethod
    async def run_plan(self, __name: str, __params: Mapping[str, Any]) -> None:
        ...

    @abstractmethod
    async def get_plans(self) -> Iterable[Plan]:
        ...


class AgnosticBlueskyController(BlueskyService):
    _context: BlueskyContext

    def __init__(self, context: BlueskyContext) -> None:
        self._context = context

    async def run_plan(self, name: str, params: Mapping[str, Any]) -> None:
        await asyncio.sleep(5)

    async def get_plans(self) -> Iterable[Plan]:
        return self._context.plans.values()


class ControllerBuilder(ABC):
    @abstractmethod
    async def run_forever(self, __controller: BlueskyService) -> None:
        ...


class BlueskyApp:
    _context: BlueskyContext
    _controller_builders: List[ControllerBuilder]

    def __init__(self, context: Optional[BlueskyContext] = None) -> None:
        self._context = context or BlueskyContext()
        self._controller_builders = []

    def plan(self, plan: PlanGenerator) -> PlanGenerator:
        schema = schema_for_func(plan)
        self._context.plans[plan.__name__] = Plan(plan.__name__, schema, plan)
        return plan

    def run(self) -> None:
        asyncio.run(self.run_async())

    async def run_async(self) -> None:
        controller = AgnosticBlueskyController(self._context)
        await asyncio.wait(
            [builder.run_forever(controller) for builder in self._controller_builders]
        )

    def control_with(self, builder: ControllerBuilder) -> None:
        self._controller_builders.append(builder)

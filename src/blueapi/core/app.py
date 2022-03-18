import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, Iterable, Mapping, Type

from apischema.metadata import skip
from bluesky.utils import Msg

from .params import schema_for_func

PlanGenerator = Callable[..., Generator[Msg, Any, None]]


@dataclass
class Plan:
    name: str
    model: Type[Any]
    func: PlanGenerator = field(metadata=skip)


@dataclass
class BlueskyContext:
    plans: Dict[str, Plan] = field(default_factory=dict)

    def plan(self, plan: PlanGenerator) -> PlanGenerator:
        schema = schema_for_func(plan)
        self.plans[plan.__name__] = Plan(plan.__name__, schema, plan)
        return plan


class BlueskyControllerBase(ABC):
    @abstractmethod
    async def run_plan(self, __name: str, __params: Mapping[str, Any]) -> None:
        ...

    @abstractmethod
    async def get_plans(self) -> Iterable[Plan]:
        ...


class BlueskyController(BlueskyControllerBase):
    _context: BlueskyContext

    def __init__(self, context: BlueskyContext) -> None:
        self._context = context

    async def run_plan(self, name: str, params: Mapping[str, Any]) -> None:
        await asyncio.sleep(5)

    async def get_plans(self) -> Iterable[Plan]:
        return self._context.plans.values()

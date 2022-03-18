import asyncio
from abc import ABC, abstractmethod
from typing import Any, Iterable, Mapping

from blueapi.worker import RunPlan, Worker

from .bluesky_types import Plan
from .context import BlueskyContext


class BlueskyControllerBase(ABC):
    @abstractmethod
    async def run_plan(self, __name: str, __params: Mapping[str, Any]) -> None:
        ...

    @abstractmethod
    async def get_plans(self) -> Iterable[Plan]:
        ...


class BlueskyController(BlueskyControllerBase):
    _context: BlueskyContext
    _worker: Worker

    def __init__(self, context: BlueskyContext) -> None:
        self._context = context

    async def run_plan(self, name: str, params: Mapping[str, Any]) -> None:
        loop = asyncio.get_running_loop()
        plan = self._context.plans[name].func(**params)
        task = RunPlan(plan)
        loop.call_soon_threadsafe(self._worker.submit_task, task)

    async def get_plans(self) -> Iterable[Plan]:
        return self._context.plans.values()

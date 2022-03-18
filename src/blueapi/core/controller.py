import asyncio
from abc import ABC, abstractmethod
from typing import Any, Iterable, Mapping

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

    def __init__(self, context: BlueskyContext) -> None:
        self._context = context

    async def run_plan(self, name: str, params: Mapping[str, Any]) -> None:
        await asyncio.sleep(5)

    async def get_plans(self) -> Iterable[Plan]:
        return self._context.plans.values()

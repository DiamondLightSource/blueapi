import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Iterable, Mapping, Optional

from bluesky import RunEngine

from blueapi.worker import RunEngineWorker, RunPlan, Worker, run_worker_in_own_thread

from .bluesky_types import Plan
from .context import BlueskyContext

LOGGER = logging.getLogger(__name__)


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

    def __init__(
        self, context: BlueskyContext, worker: Optional[Worker] = None
    ) -> None:
        self._context = context

        if worker is None:
            worker = make_default_worker()
            run_worker_in_own_thread(worker)  # TODO: Don't do this in __init__
        self._worker = worker

    async def run_plan(self, name: str, params: Mapping[str, Any]) -> None:
        LOGGER.info(f"Asked to run plan {name} with {params}")
        loop = asyncio.get_running_loop()
        plan = self._context.plans[name].func(**params)
        task = RunPlan(plan)
        loop.call_soon_threadsafe(self._worker.submit_task, task)

    async def get_plans(self) -> Iterable[Plan]:
        return self._context.plans.values()


def make_default_worker() -> Worker:
    run_engine = RunEngine(context_managers=[])
    return RunEngineWorker(run_engine)

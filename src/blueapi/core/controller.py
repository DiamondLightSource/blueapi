import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Iterable, Mapping, Optional

from bluesky import RunEngine

from blueapi.worker import RunEngineWorker, RunPlan, Worker, run_worker_in_own_thread

from .bluesky_types import Plan
from .context import AbilityRegistry, BlueskyContext

LOGGER = logging.getLogger(__name__)


class BlueskyControllerBase(ABC):
    """
    Object to control Bluesky, bridge between API and worker
    """

    @abstractmethod
    async def run_workers(self) -> None:
        ...

    @abstractmethod
    async def run_plan(self, __name: str, __params: Mapping[str, Any]) -> None:
        """
        Run a named plan with parameters

        Args:
            __name (str): The name of the plan to run
            __params (Mapping[str, Any]): The parameters for the plan in
                                          deserialized form
        """

        ...

    @abstractmethod
    async def get_plans(self) -> Iterable[Plan]:
        """
        Get a all plans that can be run

        Returns:
            Iterable[Plan]: Iterable of plans
        """

        ...

    @abstractmethod
    async def get_abilities(self) -> AbilityRegistry:
        ...


class BlueskyController(BlueskyControllerBase):
    """
    Default implementation of BlueskyControllerBase
    """

    _context: BlueskyContext
    _worker: Worker

    def __init__(
        self, context: BlueskyContext, worker: Optional[Worker] = None
    ) -> None:
        self._context = context

        if worker is None:
            worker = make_default_worker()

        self._worker = worker

    async def run_workers(self) -> None:
        run_worker_in_own_thread(self._worker)

    async def run_plan(self, name: str, params: Mapping[str, Any]) -> None:
        LOGGER.info(f"Asked to run plan {name} with {params}")
        loop = asyncio.get_running_loop()
        plan = self._context.plans[name].func(**params)
        task = RunPlan(plan)
        loop.call_soon_threadsafe(self._worker.submit_task, task)

    async def get_plans(self) -> Iterable[Plan]:
        return self._context.plans.values()

    async def get_abilities(self) -> AbilityRegistry:
        return self._context.abilities


def make_default_worker() -> Worker:
    """
    Helper function to make a worker

    Returns:
        Worker: A new worker with sensible default parameters
    """

    run_engine = RunEngine(context_managers=[])
    return RunEngineWorker(run_engine)

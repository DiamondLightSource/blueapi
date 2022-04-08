import asyncio
import logging
from typing import Any, AsyncIterable, Mapping, Optional

from bluesky import RunEngine

from blueapi.core import (
    Ability,
    AsyncEventStreamBase,
    AsyncEventStreamWrapper,
    Plan,
    create_bluesky_protocol_conversions,
    nested_deserialize_with_overrides,
)
from blueapi.utils import async_events, concurrent_future_to_aio_future
from blueapi.worker import (
    RunEngineWorker,
    RunPlan,
    Worker,
    WorkerEvent,
    run_worker_in_own_thread,
)

from .base import BlueskyControllerBase
from .context import BlueskyContext

LOGGER = logging.getLogger(__name__)


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
        await concurrent_future_to_aio_future(run_worker_in_own_thread(self._worker))

    async def run_plan(self, name: str, params: Mapping[str, Any]) -> None:
        LOGGER.info(f"Asked to run plan {name} with {params}")

        loop = asyncio.get_running_loop()
        plan = self._context.plans[name]
        plan_function = self._context.plan_functions[name]
        sanitized_params = lookup_params(self._context, plan, params)
        task = RunPlan(plan_function(**sanitized_params))
        loop.call_soon_threadsafe(self._worker.submit_task, task)

    @property
    def worker_events(self) -> AsyncEventStreamBase:
        return AsyncEventStreamWrapper(self._worker.worker_events)

    @property
    def plans(self) -> Mapping[str, Plan]:
        return self._context.plans

    @property
    def abilities(self) -> Mapping[str, Ability]:
        return self._context.abilities


def make_default_worker() -> Worker:
    """
    Helper function to make a worker

    Returns:
        Worker: A new worker with sensible default parameters
    """

    run_engine = RunEngine(context_managers=[])
    return RunEngineWorker(run_engine)


def lookup_params(
    ctx: BlueskyContext, plan: Plan, params: Mapping[str, Any]
) -> Mapping[str, Any]:
    overrides = list(
        create_bluesky_protocol_conversions(lambda name: ctx.abilities[name])
    )
    return nested_deserialize_with_overrides(plan.model, params, overrides).__dict__

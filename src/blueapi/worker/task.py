import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping

from blueapi.core import (
    BlueskyContext,
    Plan,
    create_bluesky_protocol_conversions,
    nested_deserialize_with_overrides,
)


class Task(ABC):
    """
    Object that can run with a TaskContext
    """

    @abstractmethod
    def do_task(self, ctx: BlueskyContext) -> None:
        """
        Perform the task using the context

        Args:
            ctx (TaskContext): Context for the task
        """
        ...


LOGGER = logging.getLogger(__name__)


@dataclass
class RunPlan(Task):
    """
    Task that will run a plan
    """

    name: str
    params: Mapping[str, Any]
    # plan: Generator[Msg, None, Any]

    def do_task(self, ctx: BlueskyContext) -> None:
        LOGGER.info(f"Asked to run plan {self.name} with {self.params}")

        plan = ctx.plans[self.name]
        plan_function = ctx.plan_functions[self.name]
        sanitized_params = lookup_params(ctx, plan, self.params)
        plan_generator = plan_function(**sanitized_params)
        ctx.run_engine(plan_generator)


def lookup_params(
    ctx: BlueskyContext, plan: Plan, params: Mapping[str, Any]
) -> Mapping[str, Any]:
    overrides = list(
        create_bluesky_protocol_conversions(lambda name: ctx.abilities[name])
    )
    return nested_deserialize_with_overrides(plan.model, params, overrides).__dict__

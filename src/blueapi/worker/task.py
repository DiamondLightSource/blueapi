import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping

from pydantic import BaseModel, Field, parse_obj_as

from blueapi.core import BlueskyContext, Plan
from blueapi.utils import BlueapiBaseModel


# TODO: Make a TaggedUnion
class Task(ABC, BlueapiBaseModel):
    """
    Object that can run with a TaskContext
    """

    @abstractmethod
    def do_task(self, __ctx: BlueskyContext) -> None:
        """
        Perform the task using the context

        Args:
            ctx: Context for the task, holds plans/device/etc
        """


LOGGER = logging.getLogger(__name__)


class RunPlan(Task):
    """
    Task that will run a plan
    """

    name: str = Field(description="Name of plan to run")
    params: Mapping[str, Any] = Field(
        description="Values for parameters to plan, if any", default_factory=dict
    )

    def do_task(self, ctx: BlueskyContext) -> None:
        LOGGER.info(f"Asked to run plan {self.name} with {self.params}")

        plan = ctx.plans[self.name]
        func = ctx.plan_functions[self.name]
        sanitized_params = _lookup_params(ctx, plan, self.params)
        plan_generator = func(**sanitized_params.dict())
        ctx.run_engine(plan_generator)


def _lookup_params(
    ctx: BlueskyContext, plan: Plan, params: Mapping[str, Any]
) -> BaseModel:
    """
    Checks plan parameters against context

    Args:
        ctx: Context holding plans and devices
        plan: Plan object including schema
        params: Parameter values to be validated against schema

    Returns:
        Mapping[str, Any]: _description_
    """

    model = plan.model
    return parse_obj_as(model, params)


@dataclass
class ActiveTask:
    name: str
    task: Task
    is_complete: bool = False
    is_error: bool = False

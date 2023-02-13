import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping

from pydantic import BaseModel, Field, parse_obj_as
from pydantic.decorator import ValidatedFunction

from blueapi.core import BlueskyContext, Device, create_bluesky_protocol_conversions
from blueapi.utils import nested_deserialize_with_overrides


# TODO: Make a TaggedUnion
class Task(ABC, BaseModel):
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
        sanitized_params = _lookup_params(ctx, plan, self.params)
        plan_generator = plan.call(**sanitized_params)
        ctx.run_engine(plan_generator)


def _lookup_params(
    ctx: BlueskyContext, plan: ValidatedFunction, params: Mapping[str, Any]
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

    def find_device(name: str) -> Device:
        device = ctx.find_device(name)
        if device is not None:
            return device
        else:
            raise KeyError(f"Could not find device {name}")

    overrides = list(create_bluesky_protocol_conversions(find_device))
    return nested_deserialize_with_overrides(plan.model, params, overrides).__dict__


@dataclass
class ActiveTask:
    name: str
    task: Task
    is_complete: bool = False
    is_error: bool = False

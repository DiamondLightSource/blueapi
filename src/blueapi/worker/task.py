import logging
from abc import ABC, abstractmethod
from typing import Any, Mapping, Optional

from pydantic import BaseModel, Field

from blueapi.core import BlueskyContext
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
    _sanitized_params: Optional[BaseModel] = Field(default=None)

    def set_clean_params(self, model: BaseModel):
        self._sanitized_params = model

    def do_task(self, ctx: BlueskyContext) -> None:
        LOGGER.info(f"Asked to run plan {self.name} with {self.params}")

        func = ctx.plan_functions[self.name]
        sanitized_params = self._sanitized_params or _lookup_params(ctx, self)
        plan_generator = func(**sanitized_params.dict())
        ctx.run_engine(plan_generator)


def _lookup_params(ctx: BlueskyContext, task: RunPlan) -> BaseModel:
    """
    Checks plan parameters against context

    Args:
        ctx: Context holding plans and devices
        plan: Plan object including schema
        params: Parameter values to be validated against schema

    Returns:
        Mapping[str, Any]: _description_
    """

    plan = ctx.plans[task.name]
    model = plan.model
    return model.parse_obj(task.params)

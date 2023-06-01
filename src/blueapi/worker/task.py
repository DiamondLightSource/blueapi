import logging
from typing import Any, Mapping, Optional

from pydantic import BaseModel, Field

from blueapi.core import BlueskyContext
from blueapi.utils import BlueapiBaseModel

LOGGER = logging.getLogger(__name__)


class Task(BlueapiBaseModel):
    """
    Task that will run a plan
    """

    name: str = Field(description="Name of plan to run")
    params: Mapping[str, Any] = Field(
        description="Values for parameters to plan, if any", default_factory=dict
    )
    _prepared_params: Optional[BaseModel] = None

    def prepare_params(self, ctx: BlueskyContext) -> None:
        self._ensure_params(ctx)

    def do_task(self, ctx: BlueskyContext) -> None:
        LOGGER.info(f"Asked to run plan {self.name} with {self.params}")

        func = ctx.plan_functions[self.name]
        prepared_params = self._ensure_params(ctx)
        plan_generator = func(**prepared_params.dict())
        ctx.run_engine(plan_generator)

    def _ensure_params(self, ctx: BlueskyContext) -> BaseModel:
        if self._prepared_params is None:
            self._prepared_params = _lookup_params(ctx, self)
        return self._prepared_params


# Here for backward compatibility pending
# https://github.com/DiamondLightSource/blueapi/issues/253
class RunPlan(Task):
    """
    Task that will run a plan
    """

    ...


def _lookup_params(ctx: BlueskyContext, task: Task) -> BaseModel:
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

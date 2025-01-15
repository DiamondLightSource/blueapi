import logging
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field, TypeAdapter

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

    def prepare_params(self, ctx: BlueskyContext) -> Mapping[str, Any]:
        model = _lookup_params(ctx, self)
        # Re-create dict manually to avoid nesting in model_dump output
        return {field: getattr(model, field) for field in model.__pydantic_fields__}

    def do_task(self, ctx: BlueskyContext) -> None:
        LOGGER.info(f"Asked to run plan {self.name} with {self.params}")

        func = ctx.plan_functions[self.name]
        prepared_params = self.prepare_params(ctx)
        ctx.run_engine(func(**prepared_params))


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
    adapter = TypeAdapter(model)
    return adapter.validate_python(task.params)

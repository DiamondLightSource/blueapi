import logging
from collections.abc import Mapping
from typing import Any, Self, TypedDict

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

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
    metadata: dict[str, Any] = Field(
        description="Any metadata to apply to all runs within this task",
        default_factory=dict,
    )

    def prepare_params(self, ctx: BlueskyContext) -> Mapping[str, Any]:
        try:
            model = _lookup_params(ctx, self)
            # Re-create dict manually to avoid nesting in model_dump output
            return {field: getattr(model, field) for field in model.__pydantic_fields__}
        except ValidationError as ve:
            raise TaskParameterError.from_validation_error(ve) from None

    def do_task(self, ctx: BlueskyContext) -> None:
        LOGGER.info(
            f"Asked to run plan {self.name} with {self.params} and "
            f"metadata {self.metadata} for all runs"
        )

        func = ctx.plan_functions[self.name]
        prepared_params = self.prepare_params(ctx)
        ctx.run_engine.md.update(self.metadata)
        result = ctx.run_engine(func(**prepared_params))
        if isinstance(result, tuple):  # pragma: no cover
            # this is never true if the run_engine is configured correctly
            return None
        return result.plan_result


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


class InvalidTaskParameter(TypedDict):
    loc: tuple[str | int, ...]
    msg: str | None
    type: str | None
    input: Any | None


class TaskParameterError(ValueError):
    errors: list[InvalidTaskParameter]

    def __init__(self, message: str, errors: list[InvalidTaskParameter]):
        super().__init__(message)
        self.errors = errors

    @classmethod
    def from_validation_error(cls, error: ValidationError) -> Self:
        errors = [
            InvalidTaskParameter(
                loc=e.get("loc", []),
                msg=e.get("msg", None),
                type=e.get("type", None),
                input=e.get("input", None),
            )
            for e in error.errors()
        ]
        return cls(str(error), errors)

    def __reduce__(self):
        return (self.__class__, (*self.args, self.errors))

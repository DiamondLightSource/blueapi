import logging
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field, TypeAdapter

from blueapi.core import BlueskyContext
from blueapi.utils import BlueapiBaseModel

LOGGER = logging.getLogger(__name__)


MODEL_REGISTRY: dict[str, type[BaseModel]] = {}


class Task(BlueapiBaseModel):
    """
    Task that will run a plan
    """

    name: str = Field(description="Name of plan to run")
    params: Mapping[str, Any] = Field(
        description="Values for parameters to plan, if any", default_factory=dict
    )
    metadata: Mapping[str, Any] = Field(
        description="Any metadata to apply to all runs within this task",
        default_factory=dict,
    )

    def prepare_params(self, ctx: BlueskyContext) -> Mapping[str, Any]:
        model = _lookup_params(ctx, self)
        # Re-create dict manually to avoid nesting in model_dump output
        return {field: getattr(model, field) for field in model.__pydantic_fields__}

    def do_task(self, ctx: BlueskyContext) -> None:
        LOGGER.info(
            f"Asked to run plan {self.name} with {self.params} and "
            f"metadata {self.metadata} for all runs"
        )

        func = ctx.plan_functions[self.name]
        prepared_params = self.prepare_params(ctx)
        print(prepared_params)
        ctx.run_engine.md.update(self.metadata)
        result = ctx.run_engine(func(**prepared_params))
        if isinstance(result, tuple):  # pragma: no cover
            # this is never true if the run_engine is configured correctly
            return None
        return result.plan_result


def register_model(model: type[BaseModel]) -> type[BaseModel]:
    MODEL_REGISTRY[model.__name__] = model
    return model


def restore_models(obj: Any) -> Any:
    if isinstance(obj, list):
        return [restore_models(v) for v in obj]

    if not isinstance(obj, dict):
        return obj

    # First recursively restore children
    restored = {k: restore_models(v) for k, v in obj.items()}

    type_name = restored.get("__type__")
    if isinstance(type_name, str) and type_name in MODEL_REGISTRY:
        restored.pop("__type__")

        model_cls = MODEL_REGISTRY[type_name]

        arg_names = restored.pop("__args__", None)
        if arg_names:
            args = tuple(MODEL_REGISTRY[a] for a in arg_names)
            model_cls = model_cls[*args]

        return model_cls.model_validate(restored)

    return restored


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
    # Attempt to restore the plan arguments back into a pydantic model by
    # checking against registered models.
    restored_params = restore_models(dict(task.params))

    adapter = TypeAdapter(model)
    return adapter.validate_python(restored_params)
    # return adapter.validate_python(task.params)

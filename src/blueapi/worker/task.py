import logging
from collections.abc import Mapping, Sequence
from inspect import Parameter, signature
from typing import Any

from pydantic import Field, TypeAdapter

from blueapi.core import BlueskyContext
from blueapi.utils import BlueapiBaseModel

LOGGER = logging.getLogger(__name__)


class TaskParams(BlueapiBaseModel):
    args: Sequence[Any] = []
    kwargs: Mapping[str, Any] = Field(default_factory=dict)


class Task(BlueapiBaseModel):
    """
    Task that will run a plan
    """

    name: str = Field(description="Name of plan to run")
    params: TaskParams = Field(
        description="Values for parameters to plan, if any", default_factory=TaskParams
    )
    metadata: dict[str, Any] = Field(
        description="Any metadata to apply to all runs within this task",
        default_factory=dict,
    )

    def prepare_params(
        self, ctx: BlueskyContext
    ) -> tuple[list[Any], Mapping[str, Any]]:
        return _lookup_params(ctx, self)

    def do_task(self, ctx: BlueskyContext) -> None:
        LOGGER.info(
            f"Asked to run plan {self.name} with {self.params} and "
            f"metadata {self.metadata} for all runs"
        )
        plan = ctx.plan_functions[self.name]
        prepared_args, prepared_kwargs = self.prepare_params(ctx)
        ctx.run_engine.md.update(self.metadata)
        result = ctx.run_engine(plan(*prepared_args, **prepared_kwargs))
        if isinstance(result, tuple):  # pragma: no cover
            # this is never true if the run_engine is configured correctly
            return None
        return result.plan_result


def _lookup_params(
    ctx: BlueskyContext, task: Task
) -> tuple[list[Any], Mapping[str, Any]]:
    """
    Validate and prepare the arguments for a plan.
    """
    plan = ctx.plans[task.name]
    func = ctx.plan_functions[task.name]

    sig = signature(func)
    bound = sig.bind(*task.params.args, **task.params.kwargs)

    # Only validate explicitly supplied arguments. This allows Pydantic's
    # default/default_factory to provide injected defaults.
    adapter = TypeAdapter(plan.model)
    validated = adapter.validate_python(bound.arguments)

    args: list[Any] = []
    kwargs: dict[str, Any] = {}

    for name, parameter in sig.parameters.items():
        supplied = name in bound.arguments

        if supplied:
            value = getattr(validated, name)

            match parameter.kind:
                case Parameter.POSITIONAL_ONLY:
                    args.append(value)

                case Parameter.POSITIONAL_OR_KEYWORD:
                    if name in task.params.kwargs:
                        kwargs[name] = value
                    else:
                        args.append(value)

                case Parameter.VAR_POSITIONAL:
                    args.extend(value)

                case Parameter.KEYWORD_ONLY:
                    kwargs[name] = value

                case Parameter.VAR_KEYWORD:
                    kwargs.update(value)

        else:
            # Let the generated Pydantic model provide the default.
            value = getattr(validated, name)
            kwargs[name] = value

    return args, kwargs

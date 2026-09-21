import logging
from collections.abc import Mapping, Sequence
from inspect import Parameter, signature
from typing import Any

from pydantic import Field, TypeAdapter

from blueapi.core import BlueskyContext
from blueapi.utils import BlueapiBaseModel

LOGGER = logging.getLogger(__name__)


class TaskParams(BlueapiBaseModel):
    args: Sequence[Any] = Field(default_factory=lambda: [])
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
        """
        Checks the configured plan parameters against context

        Args:
            ctx: Context holding plans and devices

        Returns:
            tuple[list[Any], Mapping[str, Any]]: The prepared parameters for the plan.
        """
        plan = ctx.plans[self.name]
        func = ctx.plan_functions[self.name]

        sig = signature(func)
        bound = sig.bind(*self.params.args, **self.params.kwargs)

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
                        if name in self.params.kwargs:
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
                # Defaults need to be materialised for ordinary parameters,
                # but variadic parameters are absent when not supplied.
                if parameter.kind in (
                    Parameter.VAR_POSITIONAL,
                    Parameter.VAR_KEYWORD,
                ):
                    continue

                value = getattr(validated, name)
                kwargs[name] = value

        return args, kwargs

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

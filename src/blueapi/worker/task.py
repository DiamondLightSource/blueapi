import logging
from collections.abc import Mapping, Sequence
from inspect import Parameter, signature
from typing import Any, Self, TypedDict

from pydantic import Field, TypeAdapter, ValidationError

from blueapi.core import BlueskyContext
from blueapi.utils import BlueapiBaseModel

LOGGER = logging.getLogger(__name__)


TaskParametersV1 = Mapping[str, Any]


class TaskParametersV2(BlueapiBaseModel):
    args: Sequence[Any] = Field(default_factory=list)
    kwargs: Mapping[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_v1(cls, param: TaskParametersV1):
        return cls(kwargs=param)


class Task(BlueapiBaseModel):
    """
    Task that will run a plan
    """

    name: str = Field(description="Name of plan to run")
    params: TaskParametersV2 = Field(
        description="Values for parameters to plan, if any",
        default_factory=TaskParametersV2,
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
            tuple[list[Any], Mapping[str, Any]]: The prepared *args and **kwargs
                                                 parameters for the plan.
        """
        plan = ctx.plans[self.name]
        func = ctx.plan_functions[self.name]

        sig = signature(func)
        bound = sig.bind_partial(*self.params.args, **self.params.kwargs)

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
                # Let the generated Pydantic model provide the default.
                value = getattr(validated, name)
                kwargs[name] = value

        return args, kwargs

    def do_task(self, ctx: BlueskyContext) -> None:
        LOGGER.info(
            f"Asked to run plan {self.name} with {self.params} and "
            f"metadata {self.metadata} for all runs"
        )
        plan = ctx.plan_functions[self.name]
        try:
            args, kwargs = self.prepare_params(ctx)
        except ValidationError as ve:
            raise TaskParameterError.from_validation_error(ve) from None
        ctx.run_engine.md.update(self.metadata)
        result = ctx.run_engine(plan(*args, **kwargs))
        if isinstance(result, tuple):  # pragma: no cover
            # this is never true if the run_engine is configured correctly
            return None
        return result.plan_result


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

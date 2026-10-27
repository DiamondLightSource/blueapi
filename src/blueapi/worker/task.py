import dataclasses
import inspect
import logging
from collections.abc import Mapping
from inspect import Parameter, signature
from typing import Any, Self, TypedDict

from pydantic import BaseModel, Field, ValidationError

from blueapi.core import BlueskyContext, is_bluesky_compatible_device_type
from blueapi.utils import BlueapiBaseModel

LOGGER = logging.getLogger(__name__)


def _is_injected_parameter(parameter: Parameter) -> bool:
    """Determine whether a parameter's string default represents injection.

    The ``inject()`` helper returns a string containing the device name (or an
    empty string for composites). However, ordinary parameters can also have
    string defaults, so the default value alone cannot identify an injected
    parameter.

    Check the annotation to distinguish Bluesky-compatible devices and
    composite models (including dataclasses) from ordinary parameters. This
    ensures that ordinary defaults are left to Python rather than being
    passed explicitly to the plan.
    """
    default = parameter.default
    # If parameter default is not str, it is not injected.
    if not isinstance(default, str):
        return False

    annotation = parameter.annotation
    return (
        is_bluesky_compatible_device_type(annotation)  # Check if annotation is device
        # Check for composite inject
        or inspect.isclass(annotation)
        and (
            issubclass(annotation, BaseModel) or (dataclasses.is_dataclass(annotation))
        )
    )


class Task(BlueapiBaseModel):
    """
    Task that will run a plan
    """

    name: str = Field(description="Name of plan to run")
    args: list[Any] = Field(
        description="Positional arguments to plan",
        default_factory=list,
        exclude_if=lambda args: not args,
    )
    params: Mapping[str, Any] = Field(
        description="Keyword arguments to plan, if any",
        default_factory=dict,
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
        try:
            return self._inner_prepare_params(ctx)
        except ValidationError as ve:
            raise TaskParameterError.from_validation_error(ve) from None
        except TypeError as te:
            raise TaskParameterError(
                "Invalid arguments to plan",
                [
                    InvalidTaskParameter(
                        loc=(), msg=str(te), type="TypeError", input=None
                    )
                ],
            ) from None

    def _inner_prepare_params(
        self, ctx: BlueskyContext
    ) -> tuple[list[Any], Mapping[str, Any]]:
        """Prepare positional and keyword arguments for a plan invocation.

        Bind the task's supplied arguments to the plan's signature, then validate
        them using the plan's Pydantic model. This also resolves injected device
        names to the corresponding devices in the context.

        Only explicitly supplied arguments and injected parameters are included
        in the returned arguments. Ordinary default values are omitted so that
        Python applies the defaults defined by the plan itself, rather than
        overriding them with defaults from the Pydantic model.

        Arguments are placed in the positional or keyword collections according
        to their parameter kinds, preserving their intended binding when the
        plan is invoked. Positional-or-keyword parameters supplied by name, and
        injected parameters that were not explicitly supplied, are passed as
        keywords to avoid changing which parameters receive their values.

        Args:
            ctx: The Bluesky context containing the registered plan and its
                associated parameter model.

        Returns:
            A tuple containing the positional arguments and keyword arguments
            to pass to the plan.
        """
        plan = ctx.plans[self.name]
        func = ctx.plan_functions[self.name]

        sig = signature(func)
        bound = sig.bind_partial(*self.args, **self.params)

        # Validate explicitly supplied arguments and resolve device names.
        validated = plan.model.model_validate(bound.arguments)

        args: list[Any] = []
        kwargs: dict[str, Any] = {}

        for name, parameter in sig.parameters.items():
            supplied = name in bound.arguments
            injected = _is_injected_parameter(parameter)

            # Let Python apply ordinary defaults itself.
            if not supplied and not injected:
                continue

            value = getattr(validated, name)

            match parameter.kind:
                case Parameter.POSITIONAL_ONLY:
                    args.append(value)
                case Parameter.VAR_POSITIONAL:
                    args.extend(value)
                case Parameter.POSITIONAL_OR_KEYWORD:
                    if name in self.params or (not supplied and injected):
                        kwargs[name] = value
                    else:
                        args.append(value)
                case Parameter.KEYWORD_ONLY:
                    kwargs[name] = value
                case Parameter.VAR_KEYWORD:
                    kwargs.update(value)

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

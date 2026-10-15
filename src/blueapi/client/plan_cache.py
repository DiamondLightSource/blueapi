import logging
from inspect import Parameter
from typing import Any

from blueapi.service.model import PlanModel, TaskParametersV2, TaskRequestV2
from blueapi.worker.event import TaskError, TaskResult, TaskStatus

from .protocols import ClientProtocol

_REPR_MAX_LENGTH = 100
_REPR_MAX_ARGS_INLINE = 3
_JSON_TYPE_MAP = {
    "string": "str",
    "integer": "int",
    "boolean": "bool",
    "number": "float",
    "object": "dict",
}

log = logging.getLogger(__name__)


class PlanFailedError(Exception):
    def __init__(self, typ: str, message: str):
        super().__init__(message)
        self._type = typ


class PlanCache:
    def __init__(self, client: ClientProtocol, plans: list[PlanModel]):
        self._cache = {
            model.name: Plan(name=model.name, model=model, client=client)
            for model in plans
        }
        for name, plan in self._cache.items():
            if name.startswith("_"):
                continue
            setattr(self, name, plan)

    def __getitem__(self, name: str) -> "Plan":
        return self._cache[name]

    def __getattr__(self, name: str) -> "Plan":
        raise AttributeError(f"No plan named '{name}' available")

    def __iter__(self):
        return iter(self._cache.values())

    def __repr__(self) -> str:
        return f"PlanCache({len(self._cache)} plans)"


class Plan:
    """Callable client-side reference to a registered BlueAPI plan."""

    def __init__(self, name, model: PlanModel, client: ClientProtocol):
        self.name = name
        self.model = model
        self._client = client
        self.__doc__ = model.description
        self.parameter_kinds = model.parameter_kinds

    def __call__(self, *args, **kwargs) -> Any:
        """Execute the plan with the supplied arguments.

        Returns:
            The result returned by the plan.

        Raises:
            PlanFailedError: If plan execution fails on the server.
            TypeError: If the supplied arguments do not match the plan
                parameter schema.
        """
        req = TaskRequestV2(
            name=self.name,
            params=self._build_args(*args, **kwargs),
            instrument_session=self._client.instrument_session,
        )
        match self._client.run_task(req):
            case TaskStatus(result=TaskResult(result=res)):
                return res
            case TaskStatus(result=TaskError(type=typ, message=msg)):
                raise PlanFailedError(typ, msg)

    @property
    def help_text(self) -> str:
        return self.model.description or f"Plan {self!r}"

    @property
    def properties(self) -> dict[str, Any]:
        return self.model.parameter_schema.get("properties", {})

    @property
    def required(self) -> list[str]:
        return self.model.parameter_schema.get("required", [])

    def _build_args(self, *args: Any, **kwargs: Any) -> TaskParametersV2:
        """Check parameters against schema and build TaskParametersV2.

        Returns:
            TaskParametersV2

        Raises:
            TypeError: If too many positional arguments, unexpected keyword
                arguments, duplicate arguments, or required arguments are
                supplied incorrectly.
        """
        log.info(
            "Building args for %s, using %s and %s",
            "[" + ",".join(self.properties) + "]",
            args,
            kwargs,
        )
        kinds = self.parameter_kinds

        positional_parameters = [
            name
            for name, kind in kinds.items()
            if kind
            in (Parameter.POSITIONAL_ONLY.name, Parameter.POSITIONAL_OR_KEYWORD.name)
        ]

        var_positional = any(
            kind == Parameter.VAR_POSITIONAL.name for kind in kinds.values()
        )
        var_keyword = any(kind == Parameter.VAR_KEYWORD.name for kind in kinds.values())

        if not var_positional and len(args) > len(positional_parameters):
            raise TypeError(
                f"{self.name}({args}) got too many arguments. "
                f"Recieved {len(args)}. Expected {len(positional_parameters)}"
            )

        # Check positional/keyword collisions.
        for name in positional_parameters[: len(args)]:
            if name in kwargs:
                raise TypeError(f"{self.name} got multiple values for {name}")

        # Keyword arguments must correspond to a named parameter, unless
        # the function has **kwargs.
        if not var_keyword:
            unexpected = set(kwargs) - set(kinds)
            if unexpected:
                raise TypeError(f"{self.name} got unexpected arguments: {unexpected}")

        # A keyword-only parameter cannot be supplied positionally.
        # Since positional_parameters excludes KEYWORD_ONLY, this is
        # automatically handled above.

        supplied = set(kwargs) | set(positional_parameters[: len(args)])

        required = {
            name
            for name in self.required
            if kinds[name]
            not in (Parameter.VAR_POSITIONAL.name, Parameter.VAR_KEYWORD.name)
        }

        if missing := required - supplied:
            raise TypeError(f"Missing argument(s) for {missing}")

        return TaskParametersV2(args=args, kwargs=kwargs)

    def __repr__(self) -> str:
        """Return a signature-like representation of the plan.

        The representation includes parameter types and defaults derived from
        the plan's JSON schema. Short signatures are rendered on one line;
        longer signatures are formatted across multiple lines.
        """
        kinds = self.model.parameter_kinds

        def _format_arg(name: str, info: dict[str, Any]) -> str:
            typ = self.model.parameter_types[name]
            kind = kinds[name]

            if kind == Parameter.VAR_POSITIONAL.name:
                return f"*{name}: {typ}"

            if kind == Parameter.VAR_KEYWORD.name:
                return f"**{name}: {typ}"

            if name in self.required:
                return f"{name}: {typ}"

            if "default" in info:
                return f"{name}: {typ} = {info['default']!r}"

            return f"{name}: {typ} = None"

        args: list[str] = []
        names = list(self.properties)

        has_var_positional = Parameter.VAR_POSITIONAL.name in kinds.values()

        for i, name in enumerate(names):
            kind = kinds[name]

            # Positional-only parameters need a "/" after the last one.
            if kind == Parameter.POSITIONAL_ONLY.name:
                args.append(_format_arg(name, self.properties[name]))

                if (
                    i + 1 == len(names)
                    or kinds[names[i + 1]] != Parameter.POSITIONAL_ONLY.name
                ):
                    args.append("/")

                continue

            # Keyword-only parameters need a "*" separator if there is
            # no *args parameter to provide the separator.
            if kind == Parameter.KEYWORD_ONLY.name and not has_var_positional:
                if not args or args[-1] != "*":
                    args.append("*")

            args.append(_format_arg(name, self.properties[name]))

        single_line = f"{self.name}({', '.join(args)})"

        if len(single_line) <= _REPR_MAX_LENGTH and len(args) <= _REPR_MAX_ARGS_INLINE:
            return single_line

        indent = "    "
        # Fall back to multiline if too many arguments or too long.
        multiline_args = ",\n".join(f"{indent}{arg}" for arg in args)
        return f"{self.name}(\n{multiline_args}\n)"

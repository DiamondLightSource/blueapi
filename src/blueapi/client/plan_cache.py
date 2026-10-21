import logging
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
    """Collection of plans that can be accessed by name or attribute."""

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

    def __init__(self, name: str, model: PlanModel, client: ClientProtocol):
        self.name = name
        self.model = model
        self._client = client
        self.__doc__ = model.description

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
        properties = list(self.properties)

        if len(args) > len(properties):
            raise TypeError(f"{self.name} got too many arguments")

        if extra := {k for k in kwargs if k not in properties}:
            raise TypeError(f"{self.name} got unexpected arguments: {extra}")

        positional_names = properties[: len(args)]

        if duplicate := set(positional_names) & kwargs.keys():
            name = next(iter(duplicate))
            raise TypeError(f"{self.name} got multiple values for {name}")

        supplied = set(positional_names) | kwargs.keys()

        if missing := set(self.required) - supplied:
            raise TypeError(f"Missing argument(s) for {missing}")

        return TaskParametersV2(args=args, kwargs=kwargs)

    def __repr__(self) -> str:
        """Return a signature-like representation of the plan.

        The representation includes parameter types and defaults derived from
        the plan's JSON schema. Short signatures are rendered on one line;
        longer signatures are formatted across multiple lines.
        """
        required = set(self.required)

        def _format_arg(name: str, info: dict[str, Any]) -> str:
            typ = _pretty_type(info)
            default = info.get("default")

            if name in required:
                return f"{name}: {typ}"
            if default := info.get("default"):
                return f"{name}: {typ} = {default!r}"
            return f"{name}: {typ} | None = None"

        args = [_format_arg(name, info) for name, info in self.properties.items()]
        single_line = f"{self.name}({', '.join(args)})"

        if len(single_line) <= _REPR_MAX_LENGTH and len(args) <= _REPR_MAX_ARGS_INLINE:
            return single_line

        indent = "    "
        # Fall back to multiline if too many arguments or too long.
        multiline_args = ",\n".join(f"{indent}{arg}" for arg in args)
        return f"{self.name}(\n{multiline_args}\n)"


def _pretty_type(schema: dict[str, Any]) -> str:
    """Convert a JSON schema type definition into a readable Python type.

    Handles references, arrays, unions, and primitive JSON schema types.
    Unknown or unsupported schemas fall back to ``Any`` where no useful type
    information is available.
    """
    if "$ref" in schema:
        return schema["$ref"].split("/")[-1]

    if schema.get("type") == "array":
        item_schema = schema.get("items", {})
        inner = _pretty_type(item_schema)
        return f"list[{inner}]"

    if "anyOf" in schema:
        return " | ".join(_pretty_type(s) for s in schema["anyOf"])

    json_type = schema.get("type")
    if isinstance(json_type, str):
        return _JSON_TYPE_MAP.get(json_type, json_type.split(".")[-1])

    return "Any"

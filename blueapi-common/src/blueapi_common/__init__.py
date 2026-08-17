import inspect
from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from inspect import Parameter
from typing import Annotated, Any, TypeVar, get_args, get_origin

from pydantic import TypeAdapter


def inject(name: str | None = None) -> Any:
    return Inject(name)


T = TypeVar("T")


@dataclass
class Inject:
    name: str | None = None


Injected = Annotated[T, Inject()]


# Sentinel to indicate no value
class Missing:
    def __repr__(self) -> str:
        return "Missing"


MISSING = Missing()


@dataclass
class RawValue:
    name: str
    passed: Any = MISSING
    default: Any = Parameter.empty
    target: type[Any] = type[Any]
    meta: tuple[Any, ...] = ()

    @cached_property
    def inject(self) -> Inject | None:
        for meta in self.meta:
            if isinstance(meta, Inject):
                return meta

    def resolve(self, lookup) -> Any:
        value = self.passed
        if value is MISSING:
            value = self.default
        if value is MISSING and (inj := self.inject):
            value = lookup(inj.name or self.name)
        if not isinstance(value, self.target):
            return TypeAdapter(self.target).validate_python(value)
        return value


# * Map args/kwargs to parameters
# * Identify missing parameters
# * Check for defaults for missing
# * Convert to expected types


def source_args(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    lookup: Callable[[str], Any],
) -> tuple[tuple, dict[str, Any]]:
    """Compile args and kwargs required to call a function"""
    sig = inspect.signature(func)
    a = []
    kw = {}

    bound = sig.bind_partial(*args, **kwargs)

    for name, para in sig.parameters.items():
        if get_origin(para.annotation) is Annotated:
            target, *meta = get_args(para.annotation)
        else:
            target, meta = para.annotation, ()
        value = RawValue(
            name=name,
            passed=bound.arguments.get(name, MISSING),
            default=MISSING if para.default is Parameter.empty else para.default,
            target=target,
            meta=tuple(meta),
        )
        match para.kind:
            case (
                Parameter.POSITIONAL_ONLY
                | Parameter.POSITIONAL_OR_KEYWORD
                | Parameter.VAR_POSITIONAL
            ):
                a.append(value)
            case Parameter.KEYWORD_ONLY | Parameter.VAR_KEYWORD:
                kw[name] = value

    return convert_args(tuple(a), kw, lookup)


def convert_args(a, kw, lookup) -> tuple[tuple[Any, ...], dict[str, Any]]:
    a = tuple(arg.resolve(lookup) for arg in a)
    kw = {k: v.resolve(lookup) for k, v in kw.items()}
    return (a, kw)

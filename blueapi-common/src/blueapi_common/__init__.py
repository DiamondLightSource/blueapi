import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from inspect import Parameter
from typing import Annotated, Any, TypeVar, get_args, get_origin

from bluesky.protocols import (
    Checkable,
    Configurable,
    Flyable,
    Movable,
    Pausable,
    Readable,
    Stageable,
    Stoppable,
    Subscribable,
    Triggerable,
    WritesExternalAssets,
)
from ophyd_async.core import Device as AsyncDevice
from pydantic import TypeAdapter

# An object that encapsulates the device to do useful things to produce
# data (e.g. move and read)
Device = (
    Checkable
    | Flyable
    | Movable
    | Pausable
    | Readable
    | Stageable
    | Stoppable
    | Subscribable
    | WritesExternalAssets
    | Configurable
    | Triggerable
    | AsyncDevice
)

# Protocols defining interface to hardware
BLUESKY_PROTOCOLS = tuple(Device.__args__)  # type: ignore


def is_bluesky_type(typ: Any) -> bool:
    return (
        typ in BLUESKY_PROTOCOLS
        or isinstance(typ, BLUESKY_PROTOCOLS)
        or (isinstance(typ, type) and issubclass(typ, AsyncDevice))
    )


log = logging.getLogger(__name__)


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
    default: Any = MISSING
    target: type[Any] = type[Any]
    meta: tuple[Any, ...] = ()

    @cached_property
    def inject(self) -> Inject | None:
        for meta in self.meta:
            if isinstance(meta, Inject):
                return meta
        # Check for the `foo: int = inject("bar")` case
        if isinstance(self.default, Inject):
            return self.default

    def resolve(self, lookup) -> Any:
        value = self.passed
        if value is MISSING and (inj := self.inject):
            value = lookup(inj.name or self.name)
        if value is MISSING and self.default is not MISSING:
            value = self.default
        print(f"{value=}, {self=}")
        if isinstance(value, str) and len(value) and is_bluesky_type(self.target):
            log.warn("Using strings as defaults for injected args is deprecated")
            print("Looking up ", value)
            value = lookup(value)
            print(value)
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

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, TypeVar


def inject(name: str | None = None) -> Any:
    return Inject(name)


T = TypeVar("T")


@dataclass
class Inject:
    name: str | None = None


Injected = Annotated[T, Inject()]


def source_args(
    func: Callable[..., Any], lookup: Callable[[str], Any]
) -> tuple[tuple, dict[str, Any]]:
    """Compile args and kwargs required to call a function"""
    return ((), {})

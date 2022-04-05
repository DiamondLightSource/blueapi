from dataclasses import dataclass
from typing import Any, Callable, Generator, Type, Union

from bluesky.protocols import (
    Checkable,
    Flyable,
    Hinted,
    Movable,
    Pausable,
    Readable,
    Stageable,
    Stoppable,
    Subscribable,
)
from bluesky.utils import Msg

MsgGenerator = Generator[Msg, Any, None]
PlanGenerator = Callable[..., MsgGenerator]

Ability = Union[
    Checkable,
    Flyable,
    Hinted,
    Movable,
    Pausable,
    Readable,
    Stageable,
    Stoppable,
    Subscribable,
]

BLUESKY_PROTOCOLS = list(Ability.__args__)  # type: ignore


@dataclass
class Plan:
    """
    A plan that can be run
    """

    name: str
    model: Type[Any]

from dataclasses import dataclass
from typing import Any, Callable, Generator, List, Mapping, Type, Union

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

PlanGenerator = Callable[..., Generator[Msg, Any, None]]

BlueskyAbility = Union[
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


@dataclass
class Plan:
    """
    A plan that can be run
    """

    name: str
    model: Type[Any]


@dataclass
class Device:
    name: str
    metadata: Mapping[str, Any]


@dataclass
class Ability:
    name: str
    devices: List[Device]
    protocols: List[str]

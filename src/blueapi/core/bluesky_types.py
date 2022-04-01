from dataclasses import dataclass
from typing import Any, Callable, Generator, List, Mapping, Type

from bluesky.utils import Msg

PlanGenerator = Callable[..., Generator[Msg, Any, None]]


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

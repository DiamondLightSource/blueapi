from dataclasses import dataclass
from typing import Any, Callable, Generator, Type

from bluesky.utils import Msg

PlanGenerator = Callable[..., Generator[Msg, Any, None]]


@dataclass
class Plan:
    """
    A plan that can be run
    """

    name: str
    model: Type[Any]

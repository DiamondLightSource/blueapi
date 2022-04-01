from dataclasses import dataclass, field
from typing import Any, Callable, Generator, Type

from apischema.metadata import skip
from bluesky.utils import Msg

PlanGenerator = Callable[..., Generator[Msg, Any, None]]


@dataclass
class Plan:
    """
    A plan that can be run
    """

    name: str
    model: Type[Any]

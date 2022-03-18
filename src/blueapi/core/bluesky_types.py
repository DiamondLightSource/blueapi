from dataclasses import dataclass, field
from typing import Any, Callable, Generator, Type

from apischema.metadata import skip
from bluesky.utils import Msg

PlanGenerator = Callable[..., Generator[Msg, Any, None]]


@dataclass
class Plan:
    name: str
    model: Type[Any]
    func: PlanGenerator = field(metadata=skip)

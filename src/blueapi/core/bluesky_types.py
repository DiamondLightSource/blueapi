from dataclasses import dataclass, field
from typing import Any, Callable, Generator, Type

from apischema.metadata import skip
from bluesky.utils import Msg

MsgGenerator = Generator[Msg, Any, None]
PlanGenerator = Callable[..., MsgGenerator]


@dataclass
class Plan:
    """
    A plan that can be run
    """

    name: str
    model: Type[Any]
    func: PlanGenerator = field(metadata=skip)

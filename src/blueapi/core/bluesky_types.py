from dataclasses import dataclass
from typing import Any, Callable, Generator, Mapping, Type, Union

from bluesky.protocols import (
    Checkable,
    Flyable,
    Hinted,
    Movable,
    Pausable,
    Readable,
    Stageable,
    Status,
    Stoppable,
    Subscribable,
)
from bluesky.utils import Msg

try:
    from typing import Protocol, runtime_checkable
except ImportError:
    from typing_extensions import Protocol, runtime_checkable  # type: ignore


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


@dataclass
class DataEvent:
    name: str
    document: Mapping[str, Any]


@runtime_checkable
class WatchableStatus(Status, Protocol):
    def watch(self, __func: Callable) -> None:
        """
        Subscribe to notifications about partial progress.
        This is useful for progress bars.

        The callback function is expected to accept the keyword aruments:
            * ``name``
            * ``current``
            * ``initial``
            * ``target``
            * ``unit``
            * ``precision``
            * ``fraction``
            * ``time_elapsed``
            * ``time_remaining``

        :param func: Callback function

        """

        ...

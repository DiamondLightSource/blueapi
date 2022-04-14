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

#: A true "plan", usually the output of a generator function
MsgGenerator = Generator[Msg, Any, None]

#: A function that generates a plan
PlanGenerator = Callable[..., MsgGenerator]

#: An object that encapsulates the ability to do useful things to produce
# data (e.g. move and read)
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

#: Protocols defining interface to hardware
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
    """
    Event representing collection of some data. Conforms to the Bluesky event model:
    https://github.com/bluesky/event-model
    """

    name: str
    document: Mapping[str, Any]


@runtime_checkable
class WatchableStatus(Status, Protocol):
    """
    A Status that can provide progress updates to subscribers
    """

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
        Args:
            __func (Callable): Callback function
        """

        ...

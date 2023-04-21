import inspect
from typing import Any, Callable, Generator, Mapping, Type, Union

from bluesky.protocols import (
    Checkable,
    Configurable,
    Flyable,
    HasHints,
    HasName,
    HasParent,
    Movable,
    Pausable,
    Readable,
    Stageable,
    Status,
    Stoppable,
    Subscribable,
    Triggerable,
    WritesExternalAssets,
)
from bluesky.utils import Msg
from pydantic import BaseModel, Field

from blueapi.utils import BlueapiBaseModel

try:
    from typing import Protocol, runtime_checkable
except ImportError:
    from typing_extensions import Protocol, runtime_checkable  # type: ignore

#: A true "plan", usually the output of a generator function
MsgGenerator = Generator[Msg, Any, None]

#: A function that generates a plan
PlanGenerator = Callable[..., MsgGenerator]

#: An object that encapsulates the device to do useful things to produce
# data (e.g. move and read)
Device = Union[
    Checkable,
    Flyable,
    HasHints,
    HasName,
    HasParent,
    Movable,
    Pausable,
    Readable,
    Stageable,
    Stoppable,
    Subscribable,
    WritesExternalAssets,
    Configurable,
    Triggerable,
]

#: Protocols defining interface to hardware
BLUESKY_PROTOCOLS = list(Device.__args__)  # type: ignore


def is_bluesky_compatible_device(obj: Any) -> bool:
    is_object = not inspect.isclass(obj)
    # We must separately check if Obj refers to an instance rather than a
    # class, as both follow the protocols but only one is a "device".
    return is_object and _follows_bluesky_protocols(obj)


def is_bluesky_compatible_device_type(cls: Type[Any]) -> bool:
    # We must separately check if Obj refers to an class rather than an
    # instance, as both follow the protocols but only one is a type.
    return inspect.isclass(cls) and _follows_bluesky_protocols(cls)


def _follows_bluesky_protocols(obj: Any) -> bool:
    return any(map(lambda protocol: isinstance(obj, protocol), BLUESKY_PROTOCOLS))


def is_bluesky_plan_generator(func: PlanGenerator) -> bool:
    return (
        hasattr(func, "__annotations__")
        and func.__annotations__.get("return") is MsgGenerator
    )


class Plan(BlueapiBaseModel):
    """
    A plan that can be run
    """

    name: str = Field(description="Referenceable name of the plan")
    model: Type[BaseModel] = Field(
        description="Validation model of the parameters for the plan"
    )


class DataEvent(BlueapiBaseModel):
    """
    Event representing collection of some data. Conforms to the Bluesky event model:
    https://github.com/bluesky/event-model
    """

    name: str
    doc: Mapping[str, Any]


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

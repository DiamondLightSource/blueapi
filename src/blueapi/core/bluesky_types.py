import inspect
from collections.abc import Callable, Generator, Mapping
from typing import (
    Any,
    Protocol,
    get_args,
    get_origin,
    get_type_hints,
    runtime_checkable,
)

from bluesky.protocols import (
    Checkable,
    Configurable,
    Flyable,
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
from bluesky.utils import Msg, MsgGenerator
from dodal.common import PlanGenerator
from ophyd_async.core import Device as AsyncDevice
from pydantic import BaseModel, Field

from blueapi.utils import BlueapiBaseModel

PlanWrapper = Callable[[MsgGenerator], MsgGenerator]

#: An object that encapsulates the device to do useful things to produce
# data (e.g. move and read)
Device = (
    Checkable
    | Flyable
    | Movable
    | Pausable
    | Readable
    | Stageable
    | Stoppable
    | Subscribable
    | WritesExternalAssets
    | Configurable
    | Triggerable
    | AsyncDevice
)

#: Protocols defining interface to hardware
BLUESKY_PROTOCOLS = tuple(Device.__args__)  # type: ignore


def is_bluesky_compatible_device(obj: Any) -> bool:
    is_object = not inspect.isclass(obj)
    # We must separately check if Obj refers to an instance rather than a
    # class, as both follow the protocols but only one is a "device".
    return is_object and _follows_bluesky_protocols(obj)


def is_bluesky_compatible_device_type(cls: type[Any]) -> bool:
    # We must separately check if Obj refers to an class rather than an
    # instance, as both follow the protocols but only one is a type.
    return inspect.isclass(cls) and _follows_bluesky_protocols(cls)


def _follows_bluesky_protocols(obj: Any) -> bool:
    return isinstance(obj, BLUESKY_PROTOCOLS)


def is_bluesky_plan_generator(func: PlanGenerator) -> bool:
    try:
        return_type = get_type_hints(func).get("return")
        return (get_origin(return_type) == Generator) and (
            get_args(return_type)[0] == Msg
        )
    except TypeError:
        # get_type_hints fails on some objects (such as Union or Optional)
        return False


class Plan(BlueapiBaseModel):
    """
    A plan that can be run
    """

    name: str = Field(description="Referenceable name of the plan")
    description: str | None = Field(
        description="Description/docstring of the plan", default=None
    )
    model: type[BaseModel] = Field(
        description="Validation model of the parameters for the plan"
    )


class DataEvent(BlueapiBaseModel):
    """
    Event representing collection of some data. Conforms to the Bluesky event model:
    https://github.com/bluesky/event-model
    """

    name: str
    doc: Mapping[str, Any]
    task_id: str


@runtime_checkable
class WatchableStatus(Status, Protocol):
    """
    A Status that can provide progress updates to subscribers
    """

    def watch(self, __func: Callable) -> None:
        """
        Subscribe to notifications about partial progress.
        This is useful for progress bars.

        The callback function is expected to accept the keyword arguments:
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

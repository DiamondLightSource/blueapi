import itertools
from typing import Any, Mapping, Optional, TypeVar

import bluesky.plan_stubs as bps
from bluesky.protocols import Movable

from blueapi.core import MsgGenerator

Group = str

T = TypeVar("T")


def set_absolute(
    movable: Movable, value: T, group: Optional[Group] = None, wait: bool = False
) -> MsgGenerator:
    """
    Set a device, wrapper for `bp.abs_set`.

    Args:
        movable (Movable): The device to set
        value (T): The new value
        group (Optional[Group], optional): The message group to associate with the
                                           setting, for sequencing. Defaults to None.
        wait (bool, optional): The group should wait until all setting is complete
                               (e.g. a motor has finished moving). Defaults to False.

    Returns:
        MsgGenerator: Plan

    Yields:
        Iterator[MsgGenerator]: Bluesky messages
    """

    return (yield from bps.abs_set(movable, value, group=group, wait=wait))


def set_relative(
    movable: Movable, value: T, group: Optional[Group] = None, wait: bool = False
) -> MsgGenerator:
    """
    Change a device, wrapper for `bp.rel_set`.

    Args:
        movable (Movable): The device to set
        value (T): The new value
        group (Optional[Group], optional): The message group to associate with the
                                           setting, for sequencing. Defaults to None.
        wait (bool, optional): The group should wait until all setting is complete
                               (e.g. a motor has finished moving). Defaults to False.

    Returns:
        MsgGenerator: Plan

    Yields:
        Iterator[MsgGenerator]: Bluesky messages
    """

    return (yield from bps.rel_set(movable, value, group=group, wait=wait))


def move(moves: Mapping[Movable, Any], group: Optional[Group] = None) -> MsgGenerator:
    """
    Move a device, wrapper for `bp.mv`.

    Args:
        moves (Mapping[Movable, Any]): Mapping of Movables to target positions
        group (Optional[Group], optional): The message group to associate with the
                                           setting, for sequencing. Defaults to None.

    Returns:
        MsgGenerator: Plan

    Yields:
        Iterator[MsgGenerator]: Bluesky messages
    """

    return (
        yield from bps.mv(*itertools.chain.from_iterable(moves.items()), group=group)
    )


def move_relative(
    moves: Mapping[Movable, Any], group: Optional[Group] = None
) -> MsgGenerator:
    """
    Move a device relative to its current position, wrapper for `bp.mvr`.

    Args:
        moves (Mapping[Movable, Any]): Mapping of Movables to target deltas
        group (Optional[Group], optional): The message group to associate with the
                                           setting, for sequencing. Defaults to None.

    Returns:
        MsgGenerator: Plan

    Yields:
        Iterator[MsgGenerator]: Bluesky messages
    """

    return (
        yield from bps.mvr(*itertools.chain.from_iterable(moves.items()), group=group)
    )


def sleep(time: float) -> MsgGenerator:
    """
    Suspend all action for a given time, wrapper for `bp.sleep`

    Args:
        time (float): Time to wait in seconds

    Returns:
        MsgGenerator: Plan

    Yields:
        Iterator[MsgGenerator]: Bluesky messages
    """

    return (yield from bps.sleep(time))


def wait(group: Optional[Group] = None) -> MsgGenerator:
    """
    Wait for a group status to complete, wrapper for `bp.wait`

    Args:
        group (Optional[Group], optional): The name of the group to wait for, defaults
                                           to None.

    Returns:
        MsgGenerator: Plan

    Yields:
        Iterator[MsgGenerator]: Bluesky messages
    """

    return (yield from bps.wait(group))

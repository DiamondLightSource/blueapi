from typing import Any, List, Mapping, Optional, Union

import bluesky.plans as bp
from bluesky.protocols import Readable
from dodal.common import MsgGenerator

"""
Wrappers for Bluesky built-in plans with type hinting and consistently named metadata
Provided here until https://github.com/bluesky/bluesky/pull/1610 is merged
"""


def count(
    detectors: List[Readable],
    num: int = 1,
    delay: Optional[Union[float, List[float]]] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> MsgGenerator:
    """
    Take `n` readings from a device
    Args:
        detectors (List[Readable]): Readable devices to read
        num (int, optional): Number of readings to take. Defaults to 1.
        delay (Optional[Union[float, List[float]]], optional): Delay between readings.
            Defaults to None.
        metadata (Optional[Mapping[str, Any]], optional): Key-value metadata to include
            in exported data. Defaults to None.
    Returns:
        MsgGenerator: Plan
    Yields:
        Iterator[MsgGenerator]: Bluesky messages
    """
    plan_args = {
        # Until release after https://github.com/bluesky/bluesky/pull/1655 is merged
        "detectors": list(map(repr, detectors)),
        "num": num,
        "delay": delay,
    }

    _md = {
        "plan_args": plan_args,
        **(metadata or {}),
    }

    yield from bp.count(detectors, num, delay=delay, md=_md)

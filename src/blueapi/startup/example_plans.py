from typing import List

from bluesky.plan_stubs import mv
from bluesky.plans import count
from bluesky.protocols import Movable, Readable
from dodal.common import inject

from blueapi.core import MsgGenerator


def stp_snapshot(
    detectors: List[Readable],
    temperature: Movable = inject("sample_temperature"),
    pressure: Movable = inject("sample_pressure"),
) -> MsgGenerator:
    """
    Moves devices for pressure and temperature (defaults fetched from the context)
    and captures a single frame from a collection of devices
    Args:
        detectors (List[Readable]): A list of devices to read while the sample is at STP
        temperature (Optional[Movable]): A device controlling temperature of the sample,
            defaults to fetching a device name "sample_temperature" from the context
        pressure (Optional[Movable]): A device controlling pressure on the sample,
            defaults to fetching a device name "sample_pressure" from the context
    Returns:
        MsgGenerator: Plan
    Yields:
        Iterator[MsgGenerator]: Bluesky messages
    """
    yield from mv({temperature: 0, pressure: 10**5})
    yield from count(detectors, 1)

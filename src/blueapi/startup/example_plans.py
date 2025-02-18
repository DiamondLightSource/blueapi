import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky.protocols import Movable, Readable
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.common.beamlines.beamline_utils import get_path_provider
from dodal.plan_stubs.wrapped import move
from dodal.plans import count

TEMP: Movable = inject("sample_temperature")
PRESS: Movable = inject("sample_pressure")


def file_writing() -> MsgGenerator[None]:
    detectors = ["d1", "d2", "d3"]
    provider = get_path_provider()

    @bpp.run_decorator()
    def inner() -> MsgGenerator[None]:
        yield from bps.sleep(0.1)
        for detector in detectors:
            path_info = provider(detector)
            print(f"{detector} -> {path_info}")
        yield from bps.sleep(0.1)

    yield from inner()


def stp_snapshot(
    detectors: list[Readable],
    temperature: Movable = TEMP,
    pressure: Movable = PRESS,
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
    yield from move({temperature: 0, pressure: 10**5})  # type: ignore
    yield from count(set(detectors), 1)

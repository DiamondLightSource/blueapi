from bluesky.protocols import Movable, Readable
from dodal.common import inject
from dodal.plan_stubs.wrapped import move
from dodal.plans import count

from blueapi.core import MsgGenerator
from blueapi.startup.example_devices import DataClassType, MotorPositions

TEMP: Movable[float] = inject("sample_temperature")
PRESS: Movable[float] = inject("sample_pressure")
MOTOR: Movable[MotorPositions] = inject("dynamic_motor")


def stp_snapshot(
    detectors: list[Readable],
    temperature: Movable[float] = TEMP,
    pressure: Movable[float] = PRESS,
) -> MsgGenerator:
    """
    Moves devices for pressure and temperature (defaults fetched from the context)
    and captures a single frame from a collection of devices

    Args:
        detectors (List[Readable]): A list of devices to read while the sample is at STP
        temperature (Optional[Movable[float]]): A device controlling temperature of the
            sample, defaults to fetching a device name "sample_temperature" from the
            context
        pressure (Optional[Movable[float]]): A device controlling pressure on the
            sample, defaults to fetching a device name "sample_pressure" from the
            context
    Returns:
        MsgGenerator: Plan
    Yields:
        Iterator[MsgGenerator]: Bluesky messages
    """
    yield from move({temperature: 0, pressure: 10**5})
    yield from count(set(detectors), 1)


def motor_plan(motor: Movable[str]) -> MsgGenerator:
    yield from []


def dataclass_motor_plan(motor: Movable[DataClassType]) -> MsgGenerator:
    yield from []

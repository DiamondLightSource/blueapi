from typing import List

from bluesky.protocols import Movable, Readable
from ophyd import Component
from ophyd.sim import Syn2DGauss, SynGauss, SynSignal

from blueapi.plans import *  # noqa: F401, F403

from ..core import MsgGenerator
from .simmotor import BrokenSynAxis, SynAxisWithMotionEvents

x = SynAxisWithMotionEvents(name="x", delay=1.0, events_per_move=8)
y = SynAxisWithMotionEvents(name="y", delay=3.0, events_per_move=24)
z = SynAxisWithMotionEvents(name="z", delay=2.0, events_per_move=16)
theta = SynAxisWithMotionEvents(
    name="theta", delay=0.2, events_per_move=12, egu="degrees"
)
x_err = BrokenSynAxis(name="x_err", timeout=1.0)
sample_pressure = SynAxisWithMotionEvents(
    name="sample_pressure", delay=30.0, events_per_move=128, egu="MPa", value=0.101
)
sample_temperature = SynSignal(
    func=lambda: ((x.position + y.position + z.position) / 1000.0) + 20.0,
    name="sample_temperature",
)
image_det = Syn2DGauss(
    name="image_det",
    motor0=x,
    motor_field0="x",
    motor1=y,
    motor_field1="y",
    center=(0, 0),
    Imax=1,
    labels={"detectors"},
)
current_det = SynGauss(
    name="current_det",
    motor=x,
    motor_field="x",
    center=0.0,
    Imax=1,
    labels={"detectors"},
)


def stp_snapshot(
    detectors: List[Readable],
    temperature: Movable = Component(Movable, "sample_temperature"),
    pressure: Movable = Component(Movable, "sample_pressure"),
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
    yield from move({temperature: 0, pressure: 10**5})  # noqa: F405
    yield from count(detectors, 1)  # noqa: F405

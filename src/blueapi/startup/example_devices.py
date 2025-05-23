from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

from bluesky.protocols import Movable
from ophyd.sim import Syn2DGauss, SynGauss, SynSignal
from ophyd_async.core import AsyncStatus

from .simmotor import BrokenSynAxis, SynAxisWithMotionEvents


def x(name="x") -> SynAxisWithMotionEvents:
    return SynAxisWithMotionEvents(name=name, delay=1.0, events_per_move=8)


def y(name="y") -> SynAxisWithMotionEvents:
    return SynAxisWithMotionEvents(name=name, delay=3.0, events_per_move=24)


def z(name="z") -> SynAxisWithMotionEvents:
    return SynAxisWithMotionEvents(name=name, delay=2.0, events_per_move=16)


def theta(name="theta") -> SynAxisWithMotionEvents:
    return SynAxisWithMotionEvents(
        name=name, delay=0.2, events_per_move=12, egu="degrees"
    )


def x_err(name="x_err") -> BrokenSynAxis:
    return BrokenSynAxis(name=name, timeout=1.0)


def sample_pressure(name="sample_pressure") -> SynAxisWithMotionEvents:
    return SynAxisWithMotionEvents(
        name=name, delay=30.0, events_per_move=128, egu="MPa", value=0.101
    )


def sample_temperature(
    x: SynAxisWithMotionEvents,
    y: SynAxisWithMotionEvents,
    z: SynAxisWithMotionEvents,
    name="sample_temperature",
) -> SynSignal:
    return SynSignal(
        func=lambda: ((x.position + y.position + z.position) / 1000.0) + 20.0,
        name=name,
    )


def image_det(
    x: SynAxisWithMotionEvents,
    y: SynAxisWithMotionEvents,
    name="image_det",
) -> Syn2DGauss:
    return Syn2DGauss(
        name=name,
        motor0=x,
        motor_field0="x",
        motor1=y,
        motor_field1="y",
        center=(0, 0),
        Imax=1,
        labels={"detectors"},
    )


def current_det(
    x: SynAxisWithMotionEvents,
    name="current_det",
) -> SynGauss:
    return SynGauss(
        name=name,
        motor=x,
        motor_field="x",
        center=0.0,
        Imax=1,
        labels={"detectors"},
    )


def unplugged_motor(name="unplugged_motor") -> SynAxisWithMotionEvents:
    raise TimeoutError(
        "This device is supposed to fail, blueapi "
        "will mark it as not present and start up regardless"
    )


ComplexType = TypeVar("ComplexType")


@dataclass
class DataClassType:
    foo: int
    bar: str


class MyDevice(Movable[ComplexType]):
    def __init__(self, name: str):
        self.name = name

    @AsyncStatus.wrap
    async def set(self, value: ComplexType): ...


class MotorPositions(str, Enum):
    foo = "bar"
    baz = "qux"


def movable_motor(name="movable_motor") -> MyDevice:
    return MyDevice[str](name=name)


class DynamicMotor(Movable[MotorPositions]):
    def __init__(self, name: str):
        self.name = name

    @AsyncStatus.wrap
    async def set(self, value: MotorPositions): ...


class DataClassMotor(Movable[DataClassType]):
    def __init__(self, name: str):
        self.name = name

    @AsyncStatus.wrap
    async def set(self, value: DataClassType): ...


def dynamic_motor(name="dynamic_motor") -> DynamicMotor:
    return DynamicMotor(name=name)


def data_class_motor(name="data_class_motor") -> DataClassMotor:
    return DataClassMotor(name=name)

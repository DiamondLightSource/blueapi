from unittest.mock import MagicMock, NonCallableMock

from dodal.common.beamlines.beamline_utils import device_factory
from dodal.utils import OphydV1Device, OphydV2Device
from ophyd import EpicsMotor
from ophyd_async.core import DEFAULT_TIMEOUT, LazyMock, StandardReadable
from ophyd_async.epics.motor import Motor


def fake_motor_bundle_b(
    fake_motor_x: EpicsMotor,
    fake_motor_y: EpicsMotor,
) -> EpicsMotor:
    return _mock_with_name("motor_bundle_b")


def fake_motor_x() -> EpicsMotor:
    return _mock_with_name("motor_x")


class DeviceA(StandardReadable):
    def __init__(self, name: str = "") -> None:
        with self.add_children_as_readables():
            self.motor = Motor("X:SIZE")
        super().__init__(name)


@device_factory(mock=True)
def device_a() -> DeviceA:
    return DeviceA()


class UnconnectableOphydDevice(OphydV1Device):
    def wait_for_connection(
        self,
        all_signals: bool = False,
        timeout: object = 2.0,
    ) -> None:
        raise RuntimeError(f"{self.name}: fake connection error for tests")


def ophyd_device() -> UnconnectableOphydDevice:
    return UnconnectableOphydDevice(name="ophyd_device")


class UnconnectableOphydAsyncDevice(OphydV2Device):
    async def connect(
        self,
        mock: bool | LazyMock = False,
        timeout: float = DEFAULT_TIMEOUT,
        force_reconnect: bool = False,
    ) -> None:
        raise RuntimeError(f"{self.name}: fake connection error for tests")


def ophyd_async_device() -> UnconnectableOphydAsyncDevice:
    return UnconnectableOphydAsyncDevice(name="ophyd_async_device")


def fake_motor_y() -> EpicsMotor:
    return _mock_with_name("motor_y")


def fake_motor_bundle_a(
    fake_motor_x: EpicsMotor,
    fake_motor_y: EpicsMotor,
) -> EpicsMotor:
    return _mock_with_name("motor_bundle_a")


def _mock_with_name(name: str) -> MagicMock:
    # mock.name must return str, cannot MagicMock(name=name)
    mock = MagicMock()
    mock.name = name

    def stop(self, success: bool = True) -> None:
        pass

    mock.stop = stop

    return mock


def wrong_return_type() -> int:
    return "str"  # type: ignore


fetchable_non_callable = NonCallableMock()
fetchable_callable = MagicMock(return_value="string")

fetchable_non_callable.__name__ = "fetchable_non_callable"
fetchable_non_callable.__module__ = fake_motor_bundle_a.__module__
fetchable_callable.__name__ = "fetchable_callable"
fetchable_callable.__module__ = fake_motor_bundle_a.__module__

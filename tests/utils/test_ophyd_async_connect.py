import asyncio
import itertools
import logging
from typing import Callable, Iterable, Tuple, Type, cast

import pytest
from ophyd_async.core import Device, DeviceVector, NotConnected, StandardReadable

from blueapi.utils import connect_ophyd_async_devices


class DummyBaseDevice(Device):
    def __init__(self) -> None:
        self.connected = False

    async def connect(self, sim=False):
        self.connected = True


class DummyDeviceThatErrorsWhenConnecting(Device):
    async def connect(self, sim: bool = False):
        raise IOError("Connection failed")


class DummyDeviceThatTimesOutWhenConnecting(StandardReadable):
    async def connect(self, sim: bool = False):
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            raise NotConnected("source: foo")


class DummyDeviceGroup(Device):
    def __init__(self, name: str) -> None:
        self.child1 = DummyBaseDevice()
        self.child2 = DummyBaseDevice()
        self.dict_with_children: DeviceVector[DummyBaseDevice] = DeviceVector(
            {123: DummyBaseDevice()}
        )
        self.set_name(name)


class DummyDeviceGroupThatTimesOut(Device):
    def __init__(self, name: str) -> None:
        self.child1 = DummyDeviceThatTimesOutWhenConnecting()
        self.set_name(name)


class DummyDeviceGroupThatErrors(Device):
    def __init__(self, name: str) -> None:
        self.child1 = DummyDeviceThatErrorsWhenConnecting()
        self.set_name(name)


class DummyDeviceGroupThatErrorsAndTimesOut(Device):
    def __init__(self, name: str) -> None:
        self.child1 = DummyDeviceThatErrorsWhenConnecting()
        self.child2 = DummyDeviceThatTimesOutWhenConnecting()
        self.set_name(name)


ALL_DEVICE_CONSTRUCTORS = [
    DummyDeviceThatErrorsWhenConnecting,
    DummyDeviceThatTimesOutWhenConnecting,
    DummyDeviceGroupThatErrors,
    DummyDeviceGroupThatTimesOut,
    DummyDeviceGroupThatErrorsAndTimesOut,
]


@pytest.mark.parametrize("device_constructor", ALL_DEVICE_CONSTRUCTORS)
async def test_device_collector_propagates_errors_and_timeouts(
    device_constructor: Callable[[str], Device]
):
    await _assert_failing_device_does_not_connect(device_constructor("test"))


@pytest.mark.parametrize(
    "device_constructor_1,device_constructor_2",
    list(itertools.permutations(ALL_DEVICE_CONSTRUCTORS, 2)),
)
async def test_device_collector_propagates_errors_and_timeouts_from_multiple_devices(
    device_constructor_1: Callable[[str], Device],
    device_constructor_2: Callable[[str], Device],
):
    await _assert_failing_devices_do_not_connect(
        [device_constructor_1("test1"), device_constructor_2("test2")]
    )


async def test_device_collector_logs_exceptions_for_raised_errors(
    caplog: pytest.LogCaptureFixture,
):
    caplog.set_level(logging.INFO)
    await _assert_failing_device_does_not_connect(DummyDeviceGroupThatErrors)
    assert caplog.records[0].message == "1 Devices raised an error:"
    assert caplog.records[1].message == "  should_fail:"
    _assert_exception_type_and_message(
        caplog.records[1],
        OSError,
        "Connection failed",
    )


async def test_device_collector_logs_exceptions_for_timeouts(
    caplog: pytest.LogCaptureFixture,
):
    caplog.set_level(logging.INFO)
    await _assert_failing_device_does_not_connect(DummyDeviceGroupThatTimesOut)
    assert caplog.records[0].message == "1 Devices did not connect:"
    assert caplog.records[1].message == "  should_fail:"
    _assert_exception_type_and_message(
        caplog.records[1],
        NotConnected,
        "child1: source: foo",
    )


async def test_device_collector_logs_exceptions_for_multiple_devices(
    caplog: pytest.LogCaptureFixture,
):
    caplog.set_level(logging.INFO)
    await _assert_failing_devices_do_not_connect(
        [
            DummyDeviceGroupThatErrorsAndTimesOut("test1"),
            DummyDeviceGroupThatErrors("test2"),
        ]
    )
    assert caplog.records[0].message == "1 Devices did not connect:"
    assert caplog.records[1].message == "  should_fail_1:"
    _assert_exception_type_and_message(
        caplog.records[1],
        OSError,
        "Connection failed",
    )
    assert caplog.records[2].message == "1 Devices raised an error:"
    assert caplog.records[3].message == "  should_fail_2:"
    _assert_exception_type_and_message(
        caplog.records[3],
        OSError,
        "Connection failed",
    )


async def _assert_failing_device_does_not_connect(
    device: Device,
) -> pytest.ExceptionInfo[NotConnected]:
    return await _assert_failing_devices_do_not_connect([device])


async def _assert_failing_devices_do_not_connect(
    devices: Iterable[Device],
) -> pytest.ExceptionInfo[NotConnected]:
    with pytest.raises(NotConnected) as excepton_info:
        await connect_ophyd_async_devices(
            devices,
            sim=True,
            timeout=0.1,
        )
    return excepton_info


def _assert_exception_type_and_message(
    record: logging.LogRecord,
    expected_type: Type[Exception],
    expected_message: str,
):
    exception_type, exception, _ = cast(
        Tuple[Type[Exception], Exception, str],
        record.exc_info,
    )
    assert expected_type is exception_type
    assert (expected_message,) == exception.args

from dodal.device_manager import DeviceManager
from ophyd_async.epics.motor import Motor

devices = DeviceManager()


@devices.factory
def failing_device() -> Motor:
    raise TimeoutError("FooBar")

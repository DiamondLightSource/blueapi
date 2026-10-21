from dodal.device_manager import DeviceManager
from ophyd_async.epics.motor import Motor

devices = DeviceManager()


@devices.factory(mock=True)
def motor() -> Motor:
    return Motor("FOO:")

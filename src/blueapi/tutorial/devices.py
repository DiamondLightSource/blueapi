from ophyd_async.sim import SimMotor

from blueapi.core.protocols import StaticDeviceManager

devices = StaticDeviceManager()

x = SimMotor(name="x")
y = SimMotor(name="y")

devices.devices["x"] = x
devices.devices["y"] = y

from dodal.common.beamlines.beamline_utils import device_factory
from ophyd_async.epics.motor import Motor


@device_factory(mock=True)
def motor() -> Motor:
    return Motor("FOO:")

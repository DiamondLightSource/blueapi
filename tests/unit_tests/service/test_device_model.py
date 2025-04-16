import pytest
from ophyd import Device as SyncDevice
from ophyd.sim import SynAxis
from ophyd_async.core import Device as AsyncDevice

from blueapi.service.model import DeviceModel, ProtocolInfo


@pytest.fixture
def sync_device() -> SyncDevice:
    class NestedDevice(SyncDevice):
        axis = SynAxis(name="branch")

    return NestedDevice(name="root")


max_depth: list[int] = [0, 1, 2, 3, -1, -2]


root_sync_device = DeviceModel(name="root", protocols=[], address="root")
branch_sync_device = (
    DeviceModel(
        name="branch",
        protocols=[
            ProtocolInfo(name="Checkable"),
            ProtocolInfo(name="Movable"),
            ProtocolInfo(name="Pausable"),
            ProtocolInfo(name="Readable"),
            ProtocolInfo(name="Stageable"),
            ProtocolInfo(name="Stoppable"),
            ProtocolInfo(name="Subscribable"),
            ProtocolInfo(name="Configurable"),
            ProtocolInfo(name="Triggerable"),
        ],
        address="root.axis",
    ),
)
leaf_sync_devices = []


@pytest.mark.parametrize("max_depth", max_depth)
def test_ophyd_depth(sync_device: SyncDevice, max_depth: int):
    response = DeviceModel.from_device_tree(sync_device, max_depth)
    if max_depth == 0 or max_depth < -1:
        assert response == [root_sync_device]
    elif max_depth == 1:
        assert response == [root_sync_device, branch_sync_device]
    else:
        assert response == [root_sync_device, branch_sync_device, *leaf_sync_devices]


root_async_device = DeviceModel(name="root", protocols=[], address="root")
branch_async_device = (
    DeviceModel(
        name="branch",
        protocols=[
            ProtocolInfo(name="Checkable"),
            ProtocolInfo(name="Movable"),
            ProtocolInfo(name="Pausable"),
            ProtocolInfo(name="Readable"),
            ProtocolInfo(name="Stageable"),
            ProtocolInfo(name="Stoppable"),
            ProtocolInfo(name="Subscribable"),
            ProtocolInfo(name="Configurable"),
            ProtocolInfo(name="Triggerable"),
        ],
        address="root.axis",
    ),
)
leaf_async_devices = []


@pytest.mark.parametrize("max_depth", max_depth)
def test_ophyd_async_depth(async_device: AsyncDevice, max_depth: int):
    response = DeviceModel.from_device_tree(async_device, max_depth)
    if max_depth == 0 or max_depth < -1:
        assert response == [root_async_device]
    elif max_depth == 1:
        assert response == [root_async_device, branch_async_device]
    else:
        assert response == [root_async_device, branch_async_device, *leaf_async_devices]

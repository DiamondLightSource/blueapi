from typing import Iterable, Tuple

from blueapi.core import Device, HasComponents

DeviceTreeNode = Tuple[Device]


def walk_devices(devices: Iterable[Device]) -> Iterable:
    for device in devices:
        yield from walk_devices(get_components(device))
        yield device


def get_components(device: Device):
    if isinstance(device, HasComponents):
        for name in device.component_names:
            yield getattr(device, name)

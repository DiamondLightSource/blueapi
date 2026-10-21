from dodal.device_manager import DeviceManager
from dodal.devices.bimorph_mirror import BimorphMirror

devices = DeviceManager()


@devices.factory(mock=True)
def oav() -> BimorphMirror:
    return BimorphMirror("BLXXI-BMRPH-01:", number_of_channels=8)

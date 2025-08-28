from dodal.common.beamlines.beamline_utils import device_factory
from dodal.devices.bimorph_mirror import BimorphMirror


@device_factory()
def oav() -> BimorphMirror:
    return BimorphMirror("BLXXI-BMRPH-01:", number_of_channels=8)

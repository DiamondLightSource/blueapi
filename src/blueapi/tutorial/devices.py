from dodal.device_manager import DeviceManager
from ophyd_async import sim

devices = DeviceManager()


@devices.fixture
def path_provider():
    from pathlib import Path

    from ophyd_async.core import AutoIncrementFilenameProvider, StaticPathProvider

    return StaticPathProvider(
        AutoIncrementFilenameProvider(base_filename="demo"),
        Path("/tmp"),
    )


@devices.fixture
def pattern_generator():
    return sim.PatternGenerator()


@devices.factory()
def stage(pattern_generator) -> sim.SimStage:
    return sim.SimStage(pattern_generator)


@devices.factory()
def det(path_provider, pattern_generator) -> sim.SimBlobDetector:
    return sim.SimBlobDetector(path_provider, pattern_generator)

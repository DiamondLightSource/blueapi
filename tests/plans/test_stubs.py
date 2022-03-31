import pytest
from bluesky import RunEngine
from bluesky.protocols import Movable

from blueapi.plans import set_absolute


@pytest.fixture
def run_engine() -> RunEngine:
    return RunEngine()


@pytest.fixture
def motor() -> Movable:
    ...


def test_set_absolute(run_engine: RunEngine, motor: Movable) -> None:
    assert motor.position == 0.0
    run_engine(set_absolute({motor: 1.0}))
    assert motor.position == 1.0

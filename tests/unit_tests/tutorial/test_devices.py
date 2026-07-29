from pathlib import Path

import pytest

from blueapi.config import ApplicationConfig, ConfigLoader
from blueapi.core.context import BlueskyContext


@pytest.fixture
def context() -> BlueskyContext:
    loader = ConfigLoader(ApplicationConfig)
    loader.use_values_from_yaml(Path("tests/unit_tests/tutorial/test_demo.yaml"))
    config: ApplicationConfig = loader.load()
    return BlueskyContext(configuration=config)


def test_devices_loaded_from_module(context):
    assert "det", "stage" in context.devices

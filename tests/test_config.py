from blueapi.config import ConfigLoader
from blueapi.utils import InvalidConfigError
from pathlib import Path
import pytest


def test_default_config_options():
    load = ConfigLoader(None)
    assert load.source is None
    assert load.config.logging.level == "INFO"


def test_config_loader_fails_if_yaml_invalid():
    with pytest.raises(InvalidConfigError):
        ConfigLoader(Path(__file__).parent / "invalid_config.yaml")

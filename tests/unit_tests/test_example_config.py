import os
from pathlib import Path

import pytest

from blueapi.config import ApplicationConfig, ConfigLoader

root = Path(__file__).parent.parent.parent
valid_example_config = root / "tests" / "unit_tests" / "valid_example_config"


@pytest.mark.parametrize("file_name", os.listdir(valid_example_config))
def test_example_config_is_valid(file_name: str):
    path = valid_example_config / file_name
    loader = ConfigLoader(ApplicationConfig)
    loader.use_values_from_yaml(path)

    loader.load()

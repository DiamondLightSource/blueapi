import os
from pathlib import Path

import pytest
import yaml
from tests.unit_tests.test_helm_chart import render_chart

from blueapi.config import ApplicationConfig, ConfigLoader

root = Path(__file__).parent.parent.parent
valid_example_config = root / "tests" / "unit_tests" / "valid_example_config"
example_helm = root / "tests" / "unit_tests" / "helm_examples"


@pytest.mark.parametrize("file_name", os.listdir(valid_example_config))
def test_example_config_is_valid(file_name: str):
    path = valid_example_config / file_name
    loader = ConfigLoader(ApplicationConfig)
    loader.use_values_from_yaml(path)

    loader.load()


@pytest.mark.parametrize("file_name", os.listdir(example_helm))
def test_example_helm_is_valid(file_name: str):
    path = example_helm / file_name
    with path.open("r") as file_io:
        values = yaml.safe_load(file_io)
    render_chart(values=values)

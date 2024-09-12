import os
import tempfile
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
import yaml
from bluesky_stomp.models import BasicAuthentication
from pydantic import BaseModel, Field

from blueapi.config import ApplicationConfig, ConfigLoader
from blueapi.utils import InvalidConfigError


class Config(BaseModel):
    foo: int
    bar: str


class ConfigWithDefaults(BaseModel):
    foo: int = 3
    bar: str = "hello world"


class NestedConfig(BaseModel):
    nested: Config
    baz: bool


class NestedConfigWithDefaults(BaseModel):
    nested: ConfigWithDefaults = Field(default_factory=ConfigWithDefaults)
    baz: bool = False


@pytest.fixture
def package_root() -> Path:
    return Path(os.path.dirname(os.path.realpath(__file__))) / "example_yaml"


@pytest.fixture
def config_yaml(package_root: Path) -> Path:
    return package_root / "config.yaml"


@pytest.fixture
def nested_config_yaml(package_root: Path) -> Path:
    return package_root / "nested_config.yaml"


@pytest.fixture
def override_config_yaml(package_root: Path) -> Path:
    return package_root / "override_config.yaml"


@pytest.fixture
def default_yaml(package_root: Path) -> Path:
    return package_root.parent.parent / "config" / "defaults.yaml"


@pytest.mark.parametrize("schema", [ConfigWithDefaults, NestedConfigWithDefaults])
def test_load_defaults(schema: type[Any]) -> None:
    loader = ConfigLoader(schema)
    assert loader.load() == schema()


def test_load_some_defaults() -> None:
    loader = ConfigLoader(ConfigWithDefaults)
    loader.use_values({"foo": 4})
    assert loader.load() == ConfigWithDefaults(foo=4)


def test_load_override_all() -> None:
    loader = ConfigLoader(ConfigWithDefaults)
    loader.use_values({"foo": 4, "bar": "hi"})
    assert loader.load() == ConfigWithDefaults(foo=4, bar="hi")


def test_load_override_all_nested() -> None:
    loader = ConfigLoader(NestedConfig)
    loader.use_values({"nested": {"foo": 4, "bar": "hi"}, "baz": True})
    assert loader.load() == NestedConfig(nested=Config(foo=4, bar="hi"), baz=True)


def test_load_defaultless_schema() -> None:
    loader = ConfigLoader(Config)
    with pytest.raises(InvalidConfigError):
        loader.load()


def test_inject_values_into_defaultless_schema() -> None:
    loader = ConfigLoader(Config)
    loader.use_values({"foo": 4, "bar": "hi"})
    assert loader.load() == Config(foo=4, bar="hi")


def test_load_yaml(config_yaml: Path) -> None:
    loader = ConfigLoader(Config)
    loader.use_values_from_yaml(config_yaml)
    assert loader.load() == Config(foo=5, bar="test string")


def test_load_yaml_nested(nested_config_yaml: Path) -> None:
    loader = ConfigLoader(NestedConfig)
    loader.use_values_from_yaml(nested_config_yaml)
    assert loader.load() == NestedConfig(
        nested=Config(foo=6, bar="other test string"), baz=True
    )


def test_load_yaml_override(override_config_yaml: Path) -> None:
    loader = ConfigLoader(ConfigWithDefaults)
    loader.use_values_from_yaml(override_config_yaml)

    assert loader.load() == ConfigWithDefaults(foo=7)


def test_error_thrown_if_schema_does_not_match_yaml(nested_config_yaml: Path) -> None:
    loader = ConfigLoader(Config)
    loader.use_values_from_yaml(nested_config_yaml)
    with pytest.raises(InvalidConfigError):
        loader.load()


@mock.patch.dict(os.environ, {"FOO": "bar"}, clear=True)
def test_auth_from_env():
    auth = BasicAuthentication(username="${FOO}", password="baz")
    assert auth.username == "bar"


@mock.patch.dict(os.environ, {"FOO": "bar", "BAZ": "qux"}, clear=True)
def test_auth_from_env_repeated_key():
    auth = BasicAuthentication(username="${FOO}", password="${FOO}")
    assert auth.username == "bar"
    assert auth.password.get_secret_value() == "bar"


@mock.patch.dict(os.environ, {"FOO": "bar"}, clear=True)
def test_auth_from_env_ignore_case():
    auth = BasicAuthentication(username="${FOO}", password="${foo}")
    assert auth.username == "bar"
    assert auth.password.get_secret_value() == "bar"


@mock.patch.dict(os.environ, {"FOO": "bar"}, clear=True)
def test_auth_from_env_throws_when_not_available():
    # Eagerly throws an exception, will fail during initial loading
    with pytest.raises(KeyError):
        BasicAuthentication(username="${BAZ}", password="baz")
    with pytest.raises(KeyError):
        BasicAuthentication(username="${baz}", passcode="baz")


def test_config_yaml_parsed():
    # Define the configuration data as a dictionary
    config_data = {
        "env": {},
        "sources": [
            {"kind": "dodal", "module": "dodal.adsim"},
            {"kind": "planFunctions", "module": "dls_bluesky_core.plans"},
            {"kind": "planFunctions", "module": "dls_bluesky_core.stubs"},
        ],
        "data_writing": {
            "visit_directory": "/dls/p38/data/2023/cm33874-1",
            "group_name": "BL38P",
        },
    }

    # Create a temporary file
    with tempfile.NamedTemporaryFile(
        suffix=".yaml", mode="w", delete=False
    ) as temp_yaml_file:
        # Write the YAML content into the file
        yaml.dump(config_data, temp_yaml_file)
        temp_yaml_file_path = temp_yaml_file.name

    # Initialize loader and load config from the YAML file
    loader = ConfigLoader(ApplicationConfig)
    loader.use_values_from_yaml(temp_yaml_file_path)
    loaded_config = loader.load()

    # Assert that the loaded configuration matches the expected values
    assert loaded_config.env.sources[0].kind == "dodal"
    assert loaded_config.data_writing.visit_directory == "/dls/p38/data/2023/cm33874-1"

    # Clean up by removing the temporary file if desired
    os.remove(temp_yaml_file_path)  # Uncomment if you want to delete the temp file

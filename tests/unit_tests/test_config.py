import json
import os
import tempfile
from collections.abc import Generator, Mapping
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
    auth = BasicAuthentication(username="${FOO}", password="baz")  # type: ignore
    assert auth.username == "bar"


@mock.patch.dict(os.environ, {"FOO": "bar", "BAZ": "qux"}, clear=True)
def test_auth_from_env_repeated_key():
    auth = BasicAuthentication(username="${FOO}", password="${FOO}")  # type: ignore
    assert auth.username == "bar"
    assert auth.password.get_secret_value() == "bar"


@mock.patch.dict(os.environ, {"FOO": "bar"}, clear=True)
def test_auth_from_env_ignore_case():
    auth = BasicAuthentication(username="${FOO}", password="${foo}")  # type: ignore
    assert auth.username == "bar"
    assert auth.password.get_secret_value() == "bar"


@mock.patch.dict(os.environ, {"FOO": "bar"}, clear=True)
def test_auth_from_env_throws_when_not_available():
    # Eagerly throws an exception, will fail during initial loading
    with pytest.raises(KeyError):
        BasicAuthentication(username="${BAZ}", password="baz")  # type: ignore
    with pytest.raises(KeyError):
        BasicAuthentication(username="${baz}", passcode="baz")  # type: ignore


def is_subset(subset: Mapping[str, Any], superset: Mapping[str, Any]) -> bool:
    """
    Recursively check if 'subset' is contained within 'superset',
    skipping nullable (None) fields in the superset.
    """
    for key, value in subset.items():
        if key not in superset:
            return False
        superset_value = superset[key]

        # If both values are dictionaries, recurse
        if isinstance(value, dict) and isinstance(superset_value, dict):
            if not is_subset(value, superset_value):
                return False
        # Check equality for non-dict values, ignoring None in superset
        elif superset_value is not None and value != superset_value:
            return False
    return True


# Parameterize the fixture to accept different config examples
@pytest.fixture
def temp_yaml_config_file(
    request: pytest.FixtureRequest,
) -> Generator[tuple[Path, dict[str, Any]]]:
    # Use the provided config data from test parameters
    config_data = request.param

    # Create a temporary YAML file with the configuration
    with tempfile.NamedTemporaryFile(
        suffix=".yaml", mode="w", delete=False
    ) as temp_yaml_file:
        yaml.dump(config_data, temp_yaml_file)
        temp_yaml_file_path = temp_yaml_file.name

    # Provide the path and the config data
    yield Path(temp_yaml_file_path), config_data

    # Cleanup after test execution
    os.remove(temp_yaml_file_path)


# Parameterized test to run with different configurations
@pytest.mark.parametrize(
    "temp_yaml_config_file",
    [
        # Different configuration examples passed to the fixture
        {
            "env": {
                "sources": [
                    {"kind": "dodal", "module": "dodal.adsim"},
                    {"kind": "planFunctions", "module": "dodal.plans"},
                    {"kind": "planFunctions", "module": "dodal.plan_stubs.wrapped"},
                ],
            },
            "api": {"host": "0.0.0.0", "port": 8000},
        },
        {
            "stomp": None,
            "env": {
                "sources": [
                    {"kind": "dodal", "module": "dodal.adsim"},
                    {"kind": "planFunctions", "module": "dodal.plans"},
                    {"kind": "planFunctions", "module": "dodal.plan_stubs.wrapped"},
                ],
                "events": {"broadcast_status_events": True},
            },
            "logging": {"level": "INFO"},
            "api": {"host": "0.0.0.0", "port": 8000, "protocol": "http"},
            "scratch": None,
        },
    ],
    indirect=True,
)
def test_config_yaml_parsed(temp_yaml_config_file):
    temp_yaml_file_path, config_data = temp_yaml_config_file

    # Initialize loader and load config from the YAML file
    loader = ConfigLoader(ApplicationConfig)
    loader.use_values_from_yaml(temp_yaml_file_path)
    loaded_config = loader.load()

    # Parse the loaded config JSON into a dictionary
    target_dict_json = json.loads(loaded_config.model_dump_json())

    # Assert that config_data is a subset of target_dict_json
    assert is_subset(config_data, target_dict_json)


@pytest.mark.parametrize(
    "temp_yaml_config_file",
    [
        # Different configuration examples passed to the fixture
        {
            "stomp": {
                "host": "localhost",
                "port": 61613,
                "auth": {"username": "guest", "password": "guest"},
            },
            "env": {
                "events": {
                    "broadcast_status_events": True,
                },
                "sources": [
                    {"kind": "dodal", "module": "dodal.adsim"},
                    {"kind": "planFunctions", "module": "dodal.plans"},
                    {"kind": "planFunctions", "module": "dodal.plan_stubs.wrapped"},
                ],
            },
            "api": {
                "host": "0.0.0.0",
                "port": 8000,
                "protocol": "http",
            },
            "logging": {"level": "INFO"},
            "scratch": {
                "root": "/tmp/scratch/blueapi",
                "repositories": [
                    {
                        "name": "dodal",
                        "remote_url": "https://github.com/DiamondLightSource/dodal.git",
                    }
                ],
            },
        },
        {
            "stomp": {
                "host": "https://rabbitmq.diamond.ac.uk",
                "port": 61613,
                "auth": {"username": "guest", "password": "guest"},
            },
            "env": {
                "sources": [
                    {"kind": "dodal", "module": "dodal.adsim"},
                    {"kind": "planFunctions", "module": "dodal.plans"},
                    {"kind": "planFunctions", "module": "dodal.plan_stubs.wrapped"},
                ],
                "events": {"broadcast_status_events": True},
            },
            "logging": {"level": "INFO"},
            "api": {"host": "0.0.0.0", "port": 8001, "protocol": "http"},
            "scratch": {
                "root": "/tmp/scratch/blueapi",
                "repositories": [
                    {
                        "name": "dodal",
                        "remote_url": "https://github.com/DiamondLightSource/dodal.git",
                    }
                ],
            },
        },
    ],
    indirect=True,
)
def test_config_yaml_parsed_complete(temp_yaml_config_file: dict):
    temp_yaml_file_path, config_data = temp_yaml_config_file

    # Initialize loader and load config from the YAML file
    loader = ConfigLoader(ApplicationConfig)
    loader.use_values_from_yaml(temp_yaml_file_path)
    loaded_config = loader.load()

    # Parse the loaded config JSON into a dictionary
    target_dict_json = json.loads(loaded_config.model_dump_json())

    assert loaded_config.stomp is not None
    assert loaded_config.stomp.auth is not None
    assert (
        loaded_config.stomp.auth.password.get_secret_value()
        == config_data["stomp"]["auth"]["password"]  # noqa: E501
    )
    # Remove the password field to not compare it again in the full dict comparison
    del target_dict_json["stomp"]["auth"]["password"]
    del config_data["stomp"]["auth"]["password"]  # noqa: E501
    # Assert that the remaining config data is identical
    assert (
        target_dict_json == config_data
    ), f"Expected config {config_data}, but got {target_dict_json}"

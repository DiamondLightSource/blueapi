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

from blueapi.config import ApplicationConfig


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
    ApplicationConfig.model_config["yaml_file"] = temp_yaml_file_path
    app_config = ApplicationConfig()  # Instantiates with customized sources

    # Parse the loaded config JSON into a dictionary
    target_dict_json = json.loads(app_config.model_dump_json())

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
    ApplicationConfig.model_config["yaml_file"] = temp_yaml_file_path
    app_config = ApplicationConfig()  # Instantiates with customized sources

    # Parse the loaded config JSON into a dictionary
    target_dict_json = json.loads(app_config.model_dump_json())

    assert app_config.stomp is not None
    assert app_config.stomp.auth is not None
    assert (
        app_config.stomp.auth.password.get_secret_value()
        == config_data["stomp"]["auth"]["password"]  # noqa: E501
    )
    # Remove the password field to not compare it again in the full dict comparison
    del target_dict_json["stomp"]["auth"]["password"]
    del config_data["stomp"]["auth"]["password"]  # noqa: E501
    # Assert that the remaining config data is identical
    assert (
        target_dict_json == config_data
    ), f"Expected config {config_data}, but got {target_dict_json}"

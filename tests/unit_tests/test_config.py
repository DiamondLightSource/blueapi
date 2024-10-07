import os
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from bluesky_stomp.models import BasicAuthentication
from pydantic import BaseModel, Field

from blueapi.config import ConfigLoader, parse_cli_context, recursively_updated_map
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
        BasicAuthentication(username="${baz}", password="baz")


def test_single_dot_notation():
    """Test with a single dot notation key."""
    ctx_params = {"BLUEAPI.config.api.host": "my_host"}
    expected = {"BLUEAPI": {"config": {"api": {"host": "my_host"}}}}
    result = parse_cli_context(ctx_params)
    assert result == expected, f"Expected {expected}, but got {result}"


def test_multiple_dot_notation():
    """Test with multiple levels of dot notation."""
    ctx_params = {
        "BLUEAPI.config.api.host": "my_host",
        "BLUEAPI.config.api.port": 8080,
        "BLUEAPI.config.logging.level": "INFO",
    }
    expected = {
        "BLUEAPI": {
            "config": {
                "api": {"host": "my_host", "port": 8080},
                "logging": {"level": "INFO"},
            }
        }
    }
    result = parse_cli_context(ctx_params)
    assert result == expected, f"Expected {expected}, but got {result}"


def test_no_dot_notation():
    """Test with keys that don't contain dots (should be ignored)."""
    ctx_params = {"stomp_host": "localhost", "BLUEAPI.config.api.host": "my_host"}
    expected = {"BLUEAPI": {"config": {"api": {"host": "my_host"}}}}
    result = parse_cli_context(ctx_params)
    assert result == expected, f"Expected {expected}, but got {result}"


def test_empty_input():
    """Test with an empty dictionary."""
    ctx_params = {}
    expected = {}
    result = parse_cli_context(ctx_params)
    assert result == expected, f"Expected {expected}, but got {result}"


def test_none_values_for_cli_context():
    """Test that None values are ignored."""
    ctx_params = {"BLUEAPI.config.api.host": None, "BLUEAPI.config.api.port": 8080}
    expected = {"BLUEAPI": {"config": {"api": {"port": 8080}}}}
    result = parse_cli_context(ctx_params)
    assert result == expected, f"Expected {expected}, but got {result}"


def test_non_overlapping_keys():
    """Test updating when no keys overlap."""
    old = {"a": 1, "b": 2}
    new = {"c": 3, "d": 4}
    expected = {"a": 1, "b": 2, "c": 3, "d": 4}
    result = recursively_updated_map(old, new)
    assert result == expected, f"Expected {expected}, but got {result}"


def test_overlapping_keys():
    """Test updating when keys overlap (non-dictionary values)."""
    old = {"a": 1, "b": 2}
    new = {"b": 3, "c": 4}
    expected = {"a": 1, "b": 3, "c": 4}
    result = recursively_updated_map(old, new)
    assert result == expected, f"Expected {expected}, but got {result}"


def test_recursive_update():
    """Test recursive update when both old and new have nested dictionaries."""
    old = {"a": {"x": 1, "y": 2}, "b": 3}
    new = {"a": {"y": 20, "z": 30}, "c": 4}
    expected = {"a": {"x": 1, "y": 20, "z": 30}, "b": 3, "c": 4}
    result = recursively_updated_map(old, new)
    assert result == expected, f"Expected {expected}, but got {result}"


def test_none_values_for_recursive_map():
    """Test that None values in the new dictionary are ignored."""
    old = {"a": 1, "b": 2}
    new = {"b": None, "c": 3}
    expected = {
        "a": 1,
        "b": 2,  # Old value remains since None is ignored
        "c": 3,
    }
    result = recursively_updated_map(old, new)
    assert result == expected, f"Expected {expected}, but got {result}"


def test_empty_new_dict():
    """Test with an empty new dictionary."""
    old = {"a": 1, "b": 2}
    new = {}
    expected = {"a": 1, "b": 2}
    result = recursively_updated_map(old, new)
    assert result == expected, f"Expected {expected}, but got {result}"


def test_empty_old_dict():
    """Test with an empty old dictionary."""
    old = {}
    new = {"a": 1, "b": 2}
    expected = {"a": 1, "b": 2}
    result = recursively_updated_map(old, new)
    assert result == expected, f"Expected {expected}, but got {result}"


def test_both_empty_dicts():
    """Test when both old and new dictionaries are empty."""
    old = {}
    new = {}
    expected = {}
    result = recursively_updated_map(old, new)
    assert result == expected, f"Expected {expected}, but got {result}"

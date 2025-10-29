import inspect
import json
import os
import tempfile
from collections.abc import Generator, Iterable, Mapping
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
import responses
import yaml
from bluesky_stomp.models import BasicAuthentication
from pydantic import BaseModel, Field

from blueapi.config import (
    CONFIG_SCHEMA_LOCATION,
    ApplicationConfig,
    ConfigLoader,
    OIDCConfig,
)
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
def env_var_config_yaml(package_root: Path) -> Path:
    return package_root / "env_var_config.yaml"


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


@mock.patch.dict(
    os.environ, {"ENV_NUM": "12345", "BAR": "bar", "ENABLE_BAZ": "False"}, clear=True
)
def test_expand_env_vars(env_var_config_yaml: Path):
    loader = ConfigLoader(NestedConfig)
    loader.use_values_from_yaml(env_var_config_yaml)
    conf = loader.load()
    assert conf.nested.foo == 12345
    assert conf.nested.bar == "interpolated_bar_value"
    assert not conf.baz


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
        elif isinstance(value, list) and isinstance(superset_value, list):
            for sub_val, sup_val in zip(value, superset_value, strict=True):
                if not is_subset(sub_val, sup_val):
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
            "api": {"url": "http://0.0.0.0:8000/"},
        },
        {
            "stomp": {"enabled": True},
            "env": {
                "sources": [
                    {"kind": "dodal", "module": "dodal.adsim"},
                    {"kind": "planFunctions", "module": "dodal.plans"},
                    {"kind": "planFunctions", "module": "dodal.plan_stubs.wrapped"},
                ],
                "events": {"broadcast_status_events": True},
            },
            "logging": {
                "level": "INFO",
                "graylog": {
                    "enabled": False,
                    "url": "tcp://graylog-log-target.diamond.ac.uk:12232/",
                },
            },
            "api": {
                "url": "http://0.0.0.0:8000/",
            },
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
                "enabled": True,
                "url": "tcp://localhost:61613/",
                "auth": {"username": "guest", "password": "guest"},
            },
            "tiled": {
                "api_key": None,
                "enabled": False,
                "url": "http://localhost:8407/",
            },
            "auth_token_path": None,
            "env": {
                "events": {
                    "broadcast_status_events": True,
                },
                "metadata": {
                    "instrument": "p01",
                },
                "sources": [
                    {"kind": "dodal", "module": "dodal.adsim", "mock": True},
                    {"kind": "planFunctions", "module": "dodal.plans"},
                    {
                        "kind": "planFunctions",
                        "module": "dodal.plan_stubs.wrapped",
                    },
                ],
            },
            "api": {
                "url": "http://0.0.0.0:8000/",
                "cors": None,
            },
            "logging": {
                "level": "INFO",
                "graylog": {
                    "enabled": False,
                    "url": "tcp://graylog-log-target.diamond.ac.uk:12232/",
                },
            },
            "numtracker": None,
            "oidc": {
                "well_known_url": "https://auth.example.com/realms/sample/.well-known/openid-configuration",
                "client_id": "blueapi-client",
                "client_audience": "aud",
                "logout_redirect_endpoint": "",
            },
            "scratch": {
                "root": "/tmp/scratch/blueapi",
                "required_gid": None,
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
                "enabled": True,
                "url": "tcp://rabbitmq.diamond.ac.uk:61613/",
                "auth": {"username": "guest", "password": "guest"},
            },
            "tiled": {
                "api_key": None,
                "enabled": False,
                "url": "http://localhost:8407/",
            },
            "auth_token_path": None,
            "env": {
                "sources": [
                    {"kind": "dodal", "module": "dodal.adsim", "mock": False},
                    {"kind": "planFunctions", "module": "dodal.plans"},
                    {
                        "kind": "planFunctions",
                        "module": "dodal.plan_stubs.wrapped",
                    },
                ],
                "events": {"broadcast_status_events": True},
                "metadata": {
                    "instrument": "p01",
                },
            },
            "logging": {
                "level": "INFO",
                "graylog": {
                    "enabled": False,
                    "url": "tcp://graylog-log-target.diamond.ac.uk:12232/",
                },
            },
            "api": {
                "url": "http://0.0.0.0:8001/",
                "cors": None,
            },
            "numtracker": None,
            "oidc": {
                "well_known_url": "https://auth.example.com/realms/sample/.well-known/openid-configuration",
                "client_id": "blueapi-client",
                "client_audience": "aud",
                "logout_redirect_endpoint": "",
            },
            "scratch": {
                "root": "/tmp/scratch/blueapi",
                "required_gid": None,
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

    assert loaded_config.stomp.auth is not None
    assert (
        loaded_config.stomp.auth.password.get_secret_value()
        == config_data["stomp"]["auth"]["password"]  # noqa: E501
    )
    # Remove the password field to not compare it again in the full dict comparison
    del target_dict_json["stomp"]["auth"]["password"]
    del config_data["stomp"]["auth"]["password"]  # noqa: E501
    # Assert that the remaining config data is identical
    assert target_dict_json == config_data, (
        f"Expected config {config_data}, but got {target_dict_json}"
    )


@pytest.mark.parametrize(
    "temp_yaml_config_file",
    [
        {
            "stomp": {
                "host": "https://rabbitmq.diamond.ac.uk",
                "port": 61613,
                "auth": {"username": "guest", "password": "guest"},
            },
            "auth_token_path": None,
            "env": {
                "sources": [
                    {"kind": "dodal", "module": "dodal.adsim"},
                    {"kind": "planFunctions", "module": "dodal.plans"},
                    {"kind": "planFunctions", "module": "dodal.plan_stubs.wrapped"},
                ],
                "events": {"broadcast_status_events": True},
                "metadata": {
                    "instrument": "p01",
                },
            },
            "logging": {"level": "INFO"},
            "api": {"host": "0.0.0.0", "port": 8001, "protocol": "http"},
            "numtracker": None,
            "oidc": {
                "well_known_url": "https://auth.example.com/realms/sample/.well-known/openid-configuration",
                "client_id": "blueapi-client",
                "client_audience": "aud",
            },
            "scratch": {
                "root": "/tmp/scratch/blueapi",
                "required_gid": None,
                "repositories": [
                    {
                        "name": "dodal",
                        "remote_url": "https://github.com/DiamondLightSource/dodal.git",
                    },
                    {
                        "name": "blueapi",
                        "remote_url": "https://github.com/DiamondLightSource/blueapi.git",
                    },
                ],
            },
        },
    ],
    indirect=True,
)
def test_raises_validation_error(temp_yaml_config_file: dict):
    temp_yaml_file_path, config_data = temp_yaml_config_file

    # Initialize loader and load config from the YAML file
    loader = ConfigLoader(ApplicationConfig)
    loader.use_values_from_yaml(temp_yaml_file_path)
    with pytest.raises(InvalidConfigError) as excinfo:
        _loaded_config = loader.load()
        assert excinfo.value.errors() == [  # type: ignore
            {
                "loc": ("scratch",),
                "msg": "The scratch area cannot be used to clone the blueapi repository. That is to prevent namespace clashing with the blueapi application.",  # noqa: E501
                "type": "value_error",
            }
        ]


def test_oauth_config_model_post_init(
    oidc_well_known: dict[str, Any],
    oidc_config: OIDCConfig,
    mock_authn_server: responses.RequestsMock,
):
    assert (
        oidc_config.device_authorization_endpoint
        == oidc_well_known["device_authorization_endpoint"]
    )
    assert (
        oidc_config.authorization_endpoint == oidc_well_known["authorization_endpoint"]
    )
    assert oidc_config.token_endpoint == oidc_well_known["token_endpoint"]
    assert oidc_config.issuer == oidc_well_known["issuer"]
    assert oidc_config.jwks_uri == oidc_well_known["jwks_uri"]
    assert oidc_config.end_session_endpoint == oidc_well_known["end_session_endpoint"]


def test_extra_fields_are_forbidden_for_application_config():
    check_no_extra_fields(ApplicationConfig)


def check_no_extra_fields(model_class: Any) -> None:
    if not inspect.isclass(model_class):
        return
    if issubclass(model_class, BaseModel):
        assert model_class.model_config.get("extra") == "forbid"
        for field in model_class.model_fields.keys():
            validate_field_annotations(model_class, field)


def validate_field_annotations(model_class: Any, model_field: str) -> None:
    field_annotation = model_class.model_fields[model_field].annotation
    extracted_annotations = getattr(field_annotation, "__args__", field_annotation)

    if isinstance(extracted_annotations, Iterable):
        for annotation in extracted_annotations:
            check_no_extra_fields(annotation)
    else:
        check_no_extra_fields(extracted_annotations)


@pytest.mark.skipif(
    not CONFIG_SCHEMA_LOCATION.exists(),
    reason="If the schema file does not exist, the test is being run"
    " with a non-editable install",
)
def test_config_schema_updated() -> None:
    with CONFIG_SCHEMA_LOCATION.open("r") as stream:
        config_schema = json.load(stream)
    assert config_schema == ApplicationConfig.model_json_schema(), (
        f"ApplicationConfig model is out of date with schema at \
            {CONFIG_SCHEMA_LOCATION}. You may need to run `blueapi config-schema -u`"
    )

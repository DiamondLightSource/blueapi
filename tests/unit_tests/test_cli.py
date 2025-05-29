import importlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from textwrap import dedent
from typing import Any, TypeVar
from unittest.mock import Mock, patch

import pytest
import responses
import yaml
from bluesky.protocols import Movable
from bluesky_stomp.messaging import StompClient
from click.testing import CliRunner
from opentelemetry import trace
from ophyd_async.core import AsyncStatus
from pydantic import BaseModel
from requests.exceptions import ConnectionError
from responses import matchers
from stomp.connect import StompConnection11 as Connection

from blueapi import __version__
from blueapi.cli.cli import main
from blueapi.cli.format import OutputFormat, fmt_dict
from blueapi.client.event_bus import BlueskyStreamingError
from blueapi.client.rest import (
    BlueskyRemoteControlError,
    InvalidParameters,
    ParameterError,
    UnauthorisedAccess,
    UnknownPlan,
)
from blueapi.config import (
    ApplicationConfig,
    ScratchConfig,
    ScratchRepository,
)
from blueapi.core.bluesky_types import DataEvent, Plan
from blueapi.service.model import (
    DeviceModel,
    DeviceResponse,
    EnvironmentResponse,
    PlanModel,
    PlanResponse,
    PythonEnvironmentResponse,
)
from blueapi.worker.event import ProgressEvent, TaskStatus, WorkerEvent, WorkerState


@pytest.fixture(autouse=True)
def reload_opentelemetry_trace_after_tests():
    """Reload opentelemetry.trace after running each test.

    OpenTelemetry only allows one global TracerProvider, however most cli entry-points
    overwrite this to set up tracing. As OpenTelemetry does not have any functions to
    aid testing, the library init has to be reloaded after each test to avoid errors.
    """
    yield
    importlib.reload(trace)


@pytest.fixture
def mock_connection() -> Mock:
    return Mock(spec=Connection)


@pytest.fixture
def mock_stomp_client(mock_connection: Mock) -> StompClient:
    return StompClient(conn=mock_connection)


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_version(runner: CliRunner):
    result = runner.invoke(main, ["--version"])
    assert result.stdout == f"blueapi, version {__version__}\n"


def test_main_no_params():
    runner = CliRunner()
    result = runner.invoke(main)
    expected = "Please invoke subcommand!\n"

    assert result.stdout == expected


@patch("blueapi.service.main.start")
@patch("blueapi.cli.scratch.setup_scratch")
@patch("blueapi.cli.cli.os.umask")
@pytest.mark.parametrize("subcommand", ["serve", "setup-scratch"])
def test_runs_with_umask_002(
    mock_umask: Mock,
    mock_setup_scratch: Mock,
    mock_start: Mock,
    runner: CliRunner,
    subcommand: str,
):
    runner.invoke(main, [subcommand])
    mock_umask.assert_called_once_with(0o002)


@patch("requests.request")
def test_connection_error_caught_by_wrapper_func(
    mock_requests: Mock, runner: CliRunner
):
    mock_requests.side_effect = ConnectionError()
    result = runner.invoke(main, ["controller", "plans"])

    assert result.stdout == "Failed to establish connection to blueapi server.\n"


@patch("requests.request")
def test_authentication_error_caught_by_wrapper_func(
    mock_requests: Mock, runner: CliRunner
):
    mock_requests.side_effect = BlueskyRemoteControlError("<Response [401]>")
    result = runner.invoke(main, ["controller", "plans"])

    assert (
        result.stdout
        == "Access denied. Please check your login status and try again.\n"
    )


@patch("requests.request")
def test_remote_error_raised_by_wrapper_func(mock_requests: Mock, runner: CliRunner):
    mock_requests.side_effect = BlueskyRemoteControlError("Response [450]")

    result = runner.invoke(main, ["controller", "plans"])
    assert (
        isinstance(result.exception, BlueskyRemoteControlError)
        and result.exception.args == ("Response [450]",)
        and result.exit_code == 1
    )


class MyModel(BaseModel):
    id: str


ComplexType = TypeVar("ComplexType")


@dataclass
class MyDevice(Movable[ComplexType]):
    name: str

    @AsyncStatus.wrap
    async def set(self, value: ComplexType): ...


@responses.activate
def test_get_plans(runner: CliRunner):
    plan = Plan(name="my-plan", model=MyModel)

    response = responses.add(
        responses.GET,
        "http://localhost:8000/plans",
        json=PlanResponse(plans=[PlanModel.from_plan(plan)]).model_dump(),
        status=200,
    )

    plans = runner.invoke(main, ["controller", "plans"])
    assert response.call_count == 1
    assert plans.output == "my-plan\n    Args\n      id=string (Required)\n"


@responses.activate
def test_get_devices(runner: CliRunner):
    device = MyDevice(name="my-device")

    response = responses.add(
        responses.GET,
        "http://localhost:8000/devices",
        json=DeviceResponse(devices=[DeviceModel.from_device(device)]).model_dump(),
        status=200,
    )

    plans = runner.invoke(main, ["controller", "devices"])
    assert response.call_count == 1
    assert plans.output == "my-device\n    Movable['ComplexType']\n"


def test_invalid_config_path_handling(runner: CliRunner):
    # test what happens if you pass an invalid config file...
    result = runner.invoke(main, ["-c", "non_existent.yaml"])
    assert result.exit_code == 1


@responses.activate
def test_submit_plan(runner: CliRunner):
    body_data = {"name": "sleep", "params": {"time": 5}}

    response = responses.post(
        url="http://a.fake.host:12345/tasks",
        match=[matchers.json_params_matcher(body_data)],
    )

    config_path = "tests/unit_tests/example_yaml/rest_and_stomp_config.yaml"
    runner.invoke(
        main, ["-c", config_path, "controller", "run", "sleep", '{"time": 5}']
    )

    assert response.call_count == 1


@responses.activate
def test_submit_plan_without_stomp(runner: CliRunner):
    config_path = "tests/unit_tests/example_yaml/rest_config.yaml"
    result = runner.invoke(
        main, ["-c", config_path, "controller", "run", "sleep", '{"time": 5}']
    )

    assert (
        result.stderr
        == "Error: Stomp configuration required to run plans is missing or disabled\n"
    )


def test_invalid_stomp_config_for_listener(runner: CliRunner):
    result = runner.invoke(main, ["controller", "listen"])
    assert isinstance(result.exception, BlueskyStreamingError)
    assert str(result.exception) == "Message bus needs to be configured"


def test_cannot_run_plans_without_stomp_config(runner: CliRunner):
    result = runner.invoke(main, ["controller", "run", "sleep", '{"time": 5}'])
    assert result.exit_code == 1
    assert (
        result.stderr
        == "Error: Stomp configuration required to run plans is missing or disabled\n"
    )


@patch("blueapi.cli.cli.StompClient")
def test_valid_stomp_config_for_listener(
    mock_stomp_client: StompClient,
    runner: CliRunner,
    mock_connection: Mock,
):
    mock_connection.is_connected.return_value = True
    result = runner.invoke(
        main,
        [
            "-c",
            "tests/unit_tests/example_yaml/valid_stomp_config.yaml",
            "controller",
            "listen",
        ],
        input="\n",
    )
    assert result.output == dedent("""\
                Subscribing to all bluesky events from localhost:61613
                Press enter to exit
                """)
    assert result.exit_code == 0


@responses.activate
def test_get_env(
    runner: CliRunner,
):
    environment_id = uuid.uuid4()
    responses.add(
        responses.GET,
        "http://localhost:8000/environment",
        json=EnvironmentResponse(
            environment_id=environment_id, initialized=True
        ).model_dump(mode="json"),
        status=200,
    )

    env = runner.invoke(main, ["controller", "env"])
    assert (
        env.output == f"environment_id=UUID('{environment_id}') "
        "initialized=True "
        "error_message=None\n"
    )


@responses.activate(assert_all_requests_are_fired=True)
@patch("blueapi.client.client.time.sleep", return_value=None)
def test_reset_env_client_behavior(
    mock_sleep: Mock,
    runner: CliRunner,
):
    environment_id = uuid.uuid4()
    responses.add(
        responses.DELETE,
        "http://localhost:8000/environment",
        json=EnvironmentResponse(
            environment_id=environment_id, initialized=False
        ).model_dump(mode="json"),
        status=200,
    )

    env_state = [False, False, True]
    environment_id = uuid.uuid4()
    for state in env_state:
        responses.add(
            responses.GET,
            "http://localhost:8000/environment",
            json=EnvironmentResponse(
                environment_id=environment_id, initialized=state
            ).model_dump(mode="json"),
            status=200,
        )

    # Invoke the CLI command that would trigger the environment initialization check
    reload_result = runner.invoke(main, ["controller", "env", "-r"])

    # Verify if sleep was called between polling iterations
    mock_sleep.assert_called()

    for index, call in enumerate(responses.calls):
        if index == 0:
            assert call.request.method == "DELETE"
            assert call.request.url == "http://localhost:8000/environment"
        else:
            assert call.request.method == "GET"
            assert call.request.url == "http://localhost:8000/environment"

    # Check if the final environment status is printed correctly
    # assert "Environment is initialized." in result.output
    assert reload_result.output == dedent(f"""\
                Reloading environment
                Environment is initialized
                environment_id=UUID('{environment_id}') initialized=True error_message=None
                """)  # noqa: E501


@responses.activate
@patch("blueapi.client.client.time.sleep", return_value=None)
def test_env_timeout(mock_sleep: Mock, runner: CliRunner):
    # Setup mocked responses for the REST endpoints
    environment_id = uuid.uuid4()
    responses.add(
        responses.DELETE,
        "http://localhost:8000/environment",
        status=200,
        json=EnvironmentResponse(
            environment_id=environment_id, initialized=False
        ).model_dump(mode="json"),
    )
    # Add responses for each polling attempt, all indicating not initialized
    responses.add(
        responses.GET,
        "http://localhost:8000/environment",
        json=EnvironmentResponse(
            environment_id=environment_id, initialized=False
        ).model_dump(mode="json"),
        status=200,
    )

    # Run the command that should interact with these endpoints
    result = runner.invoke(main, ["controller", "env", "-r", "-t", "0.1"])
    if result.exception is not None:
        assert isinstance(result.exception, TimeoutError), "Expected a TimeoutError"
        assert (
            result.exception.args[0]
            == "Failed to reload the environment within 0.1 seconds, "
            "a server restart is recommended"
        )
    else:
        raise AssertionError("Expected an exception but got None")

    # First call should be DELETE
    assert responses.calls[0].request.method == "DELETE"
    assert responses.calls[0].request.url == "http://localhost:8000/environment"

    # Remaining calls should all be GET
    for call in responses.calls[1:]:  # Skip the first DELETE request # type: ignore
        assert call.request.method == "GET"
        assert call.request.url == "http://localhost:8000/environment"

    # Check the output for the timeout message
    assert result.output == "Reloading environment\n"
    assert (
        result.exit_code == 1
    )  # Assuming your command exits successfully even on timeout for simplicity


@responses.activate
def test_env_reload_server_side_error(runner: CliRunner):
    # Setup mocked error response from the server
    responses.add(
        responses.DELETE, "http://localhost:8000/environment", status=500, json={}
    )

    result = runner.invoke(main, ["controller", "env", "-r"])
    assert isinstance(result.exception, BlueskyRemoteControlError), (
        "Expected a BlueskyRemoteError from cli runner"
    )
    assert result.exception.args[0] == "Failed to tear down the environment"

    # Check if the endpoints were hit as expected
    assert len(responses.calls) == 1  # +1 for the DELETE call

    # Only call should be DELETE
    assert responses.calls[0].request.method == "DELETE"
    assert responses.calls[0].request.url == "http://localhost:8000/environment"

    # Check the output for the timeout message
    # TODO this seems wrong but this is the current behaviour
    # There should be an error message
    assert result.output == "Reloading environment\n"

    assert result.exit_code == 1


@pytest.mark.parametrize(
    "exception, error_message",
    [
        (UnknownPlan(), "Error: Plan 'sleep' was not recognised\n"),
        (UnauthorisedAccess(), "Error: Unauthorised request\n"),
        (
            InvalidParameters(
                errors=[
                    ParameterError(
                        loc=["body", "params", "foo"],
                        type="missing",
                        msg="Foo is missing",
                        input=None,
                    )
                ]
            ),
            "Error: Incorrect parameters supplied\n    Missing value for 'foo'\n",
        ),
        (
            BlueskyRemoteControlError("Server error"),
            "Error: server error with this message: Server error\n",
        ),
        (
            ValueError("Error parsing parameters"),
            "Error: task could not run: Error parsing parameters\n",
        ),
    ],
    ids=[
        "unknown_plan",
        "unauthorised_access",
        "invalid_parameters",
        "remote_control",
        "value_error",
    ],
)
def test_error_handling(exception, error_message, runner: CliRunner):
    # Patching the create_task method to raise different exceptions
    with patch(
        "blueapi.client.rest.BlueapiRestClient.create_task", side_effect=exception
    ):
        result = runner.invoke(
            main,
            [
                "-c",
                "tests/unit_tests/example_yaml/valid_stomp_config.yaml",
                "controller",
                "run",
                "sleep",
                '{"time": 5}',
            ],
        )
    assert result.stderr == error_message
    assert result.exit_code == 1


@pytest.mark.parametrize(
    "params, error",
    [
        ("{", "Parameters are not valid JSON"),
        ("[]", ""),
    ],
)
def test_run_task_parsing_errors(params: str, error: str, runner: CliRunner):
    result = runner.invoke(
        main,
        [
            "-c",
            "tests/unit_tests/example_yaml/valid_stomp_config.yaml",
            "controller",
            "run",
            "sleep",
            params,
        ],
    )
    assert result.stderr.startswith("Error: " + error)
    assert result.exit_code == 1


def test_device_output_formatting():
    """Test for alternative device output formats"""

    device = MyDevice("my-device")

    devices = DeviceResponse(devices=[DeviceModel.from_device(device)])

    compact = dedent("""\
                my-device
                    Movable['ComplexType']
                """)

    _assert_matching_formatting(OutputFormat.COMPACT, devices, compact)

    json_out = dedent("""\
                [
                  {
                    "name": "my-device",
                    "protocols": [
                      {
                        "name": "Movable",
                        "types": [
                          "ComplexType"
                        ]
                      }
                    ]
                  }
                ]
                """)
    _assert_matching_formatting(OutputFormat.JSON, devices, json_out)
    _ = json.loads(json_out)

    full = dedent("""\
            my-device
                Movable['ComplexType']
            """)
    _assert_matching_formatting(OutputFormat.FULL, devices, full)


class ExtendedModel(BaseModel):
    name: str
    keys: list[int]
    metadata: None | Mapping[str, str] = None


def test_plan_output_formatting():
    """Test for alternative plan output formats"""

    plan = Plan(
        name="my-plan",
        description=dedent("""\
            Summary of description

            Rest of description
            """),
        model=ExtendedModel,
    )
    plans = PlanResponse(plans=[PlanModel.from_plan(plan)])

    compact = dedent("""\
                my-plan
                    Summary of description
                    Args
                      name=string (Required)
                      keys=[integer] (Required)
                      metadata=object
                """)

    _assert_matching_formatting(OutputFormat.COMPACT, plans, compact)

    json_out = dedent("""\
            [
              {
                "name": "my-plan",
                "description": "Summary of description\\n\\nRest of description\\n",
                "parameter_schema": {
                  "properties": {
                    "name": {
                      "title": "Name",
                      "type": "string"
                    },
                    "keys": {
                      "items": {
                        "type": "integer"
                      },
                      "title": "Keys",
                      "type": "array"
                    },
                    "metadata": {
                      "anyOf": [
                        {
                          "additionalProperties": {
                            "type": "string"
                          },
                          "type": "object"
                        },
                        {
                          "type": "null"
                        }
                      ],
                      "default": null,
                      "title": "Metadata"
                    }
                  },
                  "required": [
                    "name",
                    "keys"
                  ],
                  "title": "ExtendedModel",
                  "type": "object"
                }
              }
            ]
                """)
    _assert_matching_formatting(OutputFormat.JSON, plans, json_out)
    _ = json.loads(json_out)

    full = dedent("""\
        my-plan
            Summary of description

            Rest of description
            Schema
                {
                  "properties": {
                    "name": {
                      "title": "Name",
                      "type": "string"
                    },
                    "keys": {
                      "items": {
                        "type": "integer"
                      },
                      "title": "Keys",
                      "type": "array"
                    },
                    "metadata": {
                      "anyOf": [
                        {
                          "additionalProperties": {
                            "type": "string"
                          },
                          "type": "object"
                        },
                        {
                          "type": "null"
                        }
                      ],
                      "default": null,
                      "title": "Metadata"
                    }
                  },
                  "required": [
                    "name",
                    "keys"
                  ],
                  "title": "ExtendedModel",
                  "type": "object"
                }
            """)
    _assert_matching_formatting(OutputFormat.FULL, plans, full)


def test_event_formatting():
    data = DataEvent(
        name="start", doc={"foo": "bar", "fizz": {"buzz": (1, 2, 3), "hello": "world"}}
    )
    worker = WorkerEvent(
        state=WorkerState.RUNNING,
        task_status=TaskStatus(task_id="count", task_complete=False, task_failed=False),
        errors=[],
        warnings=[],
    )
    progress = ProgressEvent(task_id="start", statuses={})

    _assert_matching_formatting(
        OutputFormat.JSON,
        data,
        (
            """{"name": "start", "doc": """
            """{"foo": "bar", "fizz": {"buzz": [1, 2, 3], "hello": "world"}}}\n"""
        ),
    )
    _assert_matching_formatting(OutputFormat.COMPACT, data, "Data Event: start\n")
    _assert_matching_formatting(
        OutputFormat.FULL,
        data,
        dedent("""\
            Start:
                foo: bar
                fizz:
                    buzz: (1, 2, 3)
                    hello: world
            """),
    )

    _assert_matching_formatting(
        OutputFormat.JSON,
        worker,
        (
            """{"state": "RUNNING", "task_status": """
            """{"task_id": "count", "task_complete": false, "task_failed": false}, """
            """"errors": [], "warnings": []}\n"""
        ),
    )
    _assert_matching_formatting(OutputFormat.COMPACT, worker, "Worker Event: RUNNING\n")
    _assert_matching_formatting(
        OutputFormat.FULL,
        worker,
        "WorkerEvent: RUNNING\n    task_id: count\n",
    )

    _assert_matching_formatting(
        OutputFormat.JSON, progress, """{"task_id": "start", "statuses": {}}\n"""
    )
    _assert_matching_formatting(OutputFormat.COMPACT, progress, "Progress: ???%\n")
    _assert_matching_formatting(
        OutputFormat.FULL, progress, "Progress:\n    task_id: start\n"
    )


def test_unknown_object_formatting():
    demo = {"foo": 42, "bar": ["hello", "World"]}

    exp = """{"foo": 42, "bar": ["hello", "World"]}\n"""
    _assert_matching_formatting(OutputFormat.JSON, demo, exp)

    exp = """{'bar': ['hello', 'World'], 'foo': 42}\n"""
    _assert_matching_formatting(OutputFormat.COMPACT, demo, exp)

    _assert_matching_formatting(OutputFormat.FULL, demo, exp)


def test_dict_formatting():
    demo = {"name": "foo", "keys": [1, 2, 3], "metadata": {"fizz": "buzz"}}
    exp = """\nname: foo\nkeys: [1, 2, 3]\nmetadata:\n    fizz: buzz"""
    assert fmt_dict(demo, 0) == exp

    demo = "not a dict"
    assert fmt_dict(demo, 0) == " not a dict"


def test_generic_base_model_formatting():
    model = ExtendedModel(name="demo", keys=[1, 2, 3], metadata={"fizz": "buzz"})
    exp = '{"name": "demo", "keys": [1, 2, 3], "metadata": {"fizz": "buzz"}}\n'
    _assert_matching_formatting(OutputFormat.JSON, model, exp)

    _assert_matching_formatting(
        OutputFormat.FULL,
        model,
        dedent("""\
            ExtendedModel
                name: demo
                keys: [1, 2, 3]
                metadata:
                    fizz: buzz
            """),
    )


@patch("blueapi.cli.cli.setup_scratch")
def test_init_scratch_calls_setup_scratch(mock_setup_scratch: Mock, runner: CliRunner):
    expected_config = ScratchConfig(
        root=Path("/tmp"),
        repositories=[
            ScratchRepository(
                name="dodal",
                remote_url="https://github.com/DiamondLightSource/dodal.git",
            )
        ],
    )

    result = runner.invoke(
        main,
        ["-c", "tests/unit_tests/example_yaml/scratch.yaml", "setup-scratch"],
        input="\n",
    )
    assert result.exit_code == 0
    mock_setup_scratch.assert_called_once_with(expected_config)


def _assert_matching_formatting(fmt: OutputFormat, obj: Any, expected: str):
    output = StringIO()
    fmt.display(obj, output)
    assert expected == output.getvalue()


def test_login_success(
    runner: CliRunner,
    config_with_auth: str,
    mock_authn_server: responses.RequestsMock,
):
    with patch("webbrowser.open_new_tab", return_value=False):
        result = runner.invoke(main, ["-c", config_with_auth, "login"])
        assert (
            "Logging in\n"
            "Please login from this URL:- https://example.com/verify\n"
            "Logged in and cached new token\n" == result.output
        )
        assert result.exit_code == 0


def test_token_login_with_valid_token(
    runner: CliRunner,
    config_with_auth: str,
    mock_authn_server: responses.RequestsMock,
    cached_valid_token: Path,
):
    result = runner.invoke(main, ["-c", config_with_auth, "login"])
    assert "Logged in\n" == result.output
    assert result.exit_code == 0


def test_login_with_refresh_token(
    runner: CliRunner,
    config_with_auth: str,
    mock_authn_server: responses.RequestsMock,
    cached_valid_refresh: Path,
):
    result = runner.invoke(main, ["-c", config_with_auth, "login"])

    assert "Logged in\n" == result.output
    assert result.exit_code == 0


def test_login_when_cached_token_decode_fails(
    runner: CliRunner,
    config_with_auth: str,
    mock_authn_server: responses.RequestsMock,
    cached_expired_refresh: Path,
):
    with patch("webbrowser.open_new_tab", return_value=False):
        result = runner.invoke(main, ["-c", config_with_auth, "login"])
        assert (
            "Logging in\n"
            "Please login from this URL:- https://example.com/verify\n"
            "Logged in and cached new token\n" in result.output
        )
        assert result.exit_code == 0


def test_login_with_unauthenticated_server(
    runner: CliRunner,
    config_with_auth: str,
    mock_unauthenticated_server: responses.RequestsMock,
):
    result = runner.invoke(main, ["-c", config_with_auth, "login"])
    assert "Server is not configured to use authentication!\n" == result.output
    assert result.exit_code == 0


def test_logout_success(
    runner: CliRunner,
    config_with_auth: str,
    cached_valid_refresh: Path,
    mock_authn_server: responses.RequestsMock,
):
    assert cached_valid_refresh.exists()
    result = runner.invoke(main, ["-c", config_with_auth, "logout"])
    assert "Logged out" in result.output
    assert not cached_valid_refresh.exists()


def test_logout_invalid_token(runner: CliRunner):
    with patch("blueapi.cli.cli.SessionManager") as sm:
        sm.from_cache.side_effect = ValueError("Invalid token")
        result = runner.invoke(main, ["logout"])

    assert result.exit_code == 1
    assert (
        result.output
        == "Error: Login token is not valid - remove before trying again\n"
    )


def test_logout_unknown_error(runner: CliRunner):
    with patch("blueapi.cli.cli.SessionManager") as sm:
        sm.from_cache.side_effect = Exception("Invalid token")
        result = runner.invoke(main, ["logout"])

    assert result.exit_code == 1
    assert result.output == "Error: Error logging out: Invalid token\n"


def test_logout_when_no_cache(
    runner: CliRunner,
    config_with_auth: str,
):
    result = runner.invoke(main, ["-c", config_with_auth, "logout"])
    assert "Logged out" in result.output


def test_local_cache_cleared_on_logout_when_oidc_unavailable(
    runner: CliRunner,
    config_with_auth: str,
    cached_valid_refresh: Path,
):
    assert cached_valid_refresh.exists()
    result = runner.invoke(main, ["-c", config_with_auth, "logout"])
    assert (
        "An unexpected error occurred while attempting to log out from the server."
        in result.output
    )
    assert not cached_valid_refresh.exists()


def test_wrapper_is_a_directory_error(
    runner: CliRunner, mock_authn_server: responses.RequestsMock, tmp_path
):
    config: ApplicationConfig = ApplicationConfig(auth_token_path=tmp_path)
    config_path = tmp_path / "config.yaml"
    with open(config_path, mode="w") as valid_auth_config_file:
        valid_auth_config_file.write(yaml.dump(config.model_dump()))
    result = runner.invoke(main, ["-c", config_path.as_posix(), "login"])
    assert (
        "Invalid path: a directory path was provided instead of a file path\n"
        == result.stdout
    )


def test_wrapper_permission_error(
    runner: CliRunner, mock_authn_server: responses.RequestsMock, tmp_path
):
    token_file: Path = tmp_path / "dir/token"

    config: ApplicationConfig = ApplicationConfig(auth_token_path=token_file)
    config_path = tmp_path / "config.yaml"
    with open(config_path, mode="w") as valid_auth_config_file:
        valid_auth_config_file.write(yaml.dump(config.model_dump()))
    with patch.object(Path, "write_text", side_effect=PermissionError):
        result = runner.invoke(main, ["-c", config_path.as_posix(), "login"])
    assert f"Permission denied: Cannot write to {token_file}\n" == result.stdout


@responses.activate
def test_get_python_environment(runner: CliRunner):
    scratch_config = {
        "installed_packages": [
            {
                "name": "bar",
                "version": "0.0.1",
                "location": "/tmp/bar",
                "is_dirty": "false",
                "source": "pypi",
            },
            {
                "name": "foo",
                "version": "https://github.com/example/foo.git @18ec206e",
                "location": "/tmp/foo",
                "is_dirty": "true",
                "source": "scratch",
            },
        ],
        "scratch_enabled": "true",
    }
    response = responses.add(
        responses.GET,
        "http://localhost:8000/python_environment",
        json=scratch_config,
        status=200,
    )

    result = runner.invoke(main, ["controller", "get-python-env"])
    assert response.call_count == 1
    assert result.exit_code == 0

    assert result.output == dedent("""\
        Scratch Status: enabled
        - bar @ (0.0.1)
        - foo @ (https://github.com/example/foo.git @18ec206e) (Dirty) (Scratch)
        """)


@responses.activate
def test_get_python_env_with_empty_response(runner: CliRunner):
    scratch_config = {
        "installed_packages": [],
    }
    response = responses.add(
        responses.GET,
        "http://localhost:8000/python_environment",
        json=scratch_config,
        status=200,
    )

    result = runner.invoke(main, ["controller", "get-python-env"])
    assert response.call_count == 1
    assert result.exit_code == 0
    assert result.output == dedent("""\
    Scratch Status: disabled
    No scratch packages found
    """)


def test_python_env_output_formatting():
    """Test for alternative python env output formats"""

    python_env_response = {
        "installed_packages": [
            {
                "name": "bar",
                "version": "0.0.1",
                "location": "/tmp/bar",
                "is_dirty": "false",
                "source": "pypi",
            },
            {
                "name": "foo",
                "version": "https://github.com/example/foo.git @18ec206e",
                "location": "/tmp/foo",
                "is_dirty": "true",
                "source": "scratch",
            },
        ],
        "scratch_enabled": "true",
    }
    python_env_response = PythonEnvironmentResponse(**python_env_response)

    compact = dedent("""\
        Scratch Status: enabled
        - bar @ (0.0.1)
        - foo @ (https://github.com/example/foo.git @18ec206e) (Dirty) (Scratch)
        """)

    _assert_matching_formatting(OutputFormat.COMPACT, python_env_response, compact)

    full = dedent("""\
        Scratch Status: enabled
        Installed Packages:
        - bar
        Version: 0.0.1
        Location: /tmp/bar
        Source: pypi
        Dirty: False
        - foo
        Version: https://github.com/example/foo.git @18ec206e
        Location: /tmp/foo
        Source: scratch
        Dirty: True
        """)

    _assert_matching_formatting(OutputFormat.FULL, python_env_response, full)

    empty_python_env = PythonEnvironmentResponse(
        installed_packages=[], scratch_enabled=False
    )

    full = dedent("""\
        Scratch Status: disabled
        No scratch packages found
        """)

    _assert_matching_formatting(OutputFormat.FULL, empty_python_env, full)

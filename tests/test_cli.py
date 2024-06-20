from dataclasses import dataclass
from unittest.mock import MagicMock, Mock, patch

import pytest
import responses
from click.testing import CliRunner
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError
from requests.exceptions import ConnectionError

from blueapi import __version__
from blueapi.cli.cli import main
from blueapi.cli.event_bus_client import BlueskyRemoteError
from blueapi.core.bluesky_types import Plan
from blueapi.service.handler import Handler, teardown_handler
from blueapi.service.model import EnvironmentResponse


@pytest.fixture(autouse=True)
def ensure_handler_teardown(request):
    yield
    if "handler" in request.keywords:
        teardown_handler()


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


@patch("requests.request")
def test_connection_error_caught_by_wrapper_func(mock_requests: Mock):
    mock_requests.side_effect = ConnectionError()
    runner = CliRunner()
    result = runner.invoke(main, ["controller", "plans"])

    assert result.stdout == "Failed to establish connection to FastAPI server.\n"


# Some CLI commands require the rest api to be running...


class MyModel(BaseModel):
    id: str


@dataclass
class MyDevice:
    name: str


@pytest.mark.handler
@patch("blueapi.service.handler.Handler")
@patch("requests.request")
def test_get_plans_and_devices(
    mock_requests: Mock,
    mock_handler: Mock,
    handler: Handler,
    client: TestClient,
    runner: CliRunner,
):
    """Integration test to test get_plans and get_devices."""

    # needed so that the handler is instantiated as MockHandler() instead of Handler().
    mock_handler.side_effect = Mock(return_value=handler)

    # Setup the (Mock)Handler.
    with patch("uvicorn.run", side_effect=None):
        result = runner.invoke(main, ["serve"])

    assert result.exit_code == 0

    # Put a plan in handler.context manually.
    plan = Plan(name="my-plan", model=MyModel)
    handler._context.plans = {"my-plan": plan}

    # Setup requests.get call to return the output of the FastAPI call for plans.
    # Call the CLI function and check the output.
    mock_requests.return_value = client.get("/plans")
    plans = runner.invoke(main, ["controller", "plans"])

    assert (
        plans.output == "{'plans': [{'description': None,\n"
        "            'name': 'my-plan',\n"
        "            'parameter_schema': {'properties': {'id': {'title': 'Id',\n"
        "                                                       'type': 'string'}},\n"
        "                                 'required': ['id'],\n"
        "                                 'title': 'MyModel',\n"
        "                                 'type': 'object'}}]}\n"
    )

    # Setup requests.get call to return the output of the FastAPI call for devices.
    # Call the CLI function and check the output - expect nothing as no devices set.
    handler._context.devices = {}
    mock_requests.return_value = client.get("/devices")
    unset_devices = runner.invoke(main, ["controller", "devices"])
    assert unset_devices.output == "{'devices': []}\n"

    # Put a device in handler.context manually.
    device = MyDevice("my-device")
    handler._context.devices = {"my-device": device}

    # Setup requests.get call to return the output of the FastAPI call for devices.
    # Call the CLI function and check the output.
    mock_requests.return_value = client.get("/devices")
    devices = runner.invoke(main, ["controller", "devices"])

    assert (
        devices.output
        == "{'devices': [{'name': 'my-device', 'protocols': ['HasName']}]}\n"
    )


def test_invalid_config_path_handling(runner: CliRunner):
    # test what happens if you pass an invalid config file...
    result = runner.invoke(main, ["-c", "non_existent.yaml"])
    assert result.exit_code == 1


@pytest.mark.handler
@patch("blueapi.service.handler.Handler")
@patch("requests.request")
def test_config_passed_down_to_command_children(
    mock_requests: Mock,
    mock_handler: Mock,
    handler: Handler,
    runner: CliRunner,
):
    mock_handler.side_effect = Mock(return_value=handler)
    config_path = "tests/example_yaml/rest_config.yaml"

    with patch("uvicorn.run", side_effect=None):
        result = runner.invoke(main, ["-c", config_path, "serve"])

    assert result.exit_code == 0

    mock_requests.return_value = Mock()

    runner.invoke(
        main, ["-c", config_path, "controller", "run", "sleep", '{"time": 5}']
    )

    assert mock_requests.call_args[0] == (
        "POST",
        "http://a.fake.host:12345/tasks",
    )
    assert mock_requests.call_args[1] == {
        "json": {
            "name": "sleep",
            "params": {"time": 5},
        }
    }


def test_invalid_stomp_config_for_listener(runner: CliRunner):
    result = runner.invoke(main, ["controller", "listen"])
    assert (
        isinstance(result.exception, RuntimeError)
        and str(result.exception) == "Message bus needs to be configured"
    )


def test_cannot_run_plans_without_stomp_config(runner: CliRunner):
    result = runner.invoke(main, ["controller", "run", "sleep", '{"time": 5}'])
    assert result.exit_code == 1
    assert (
        isinstance(result.exception, RuntimeError)
        and str(result.exception)
        == "Cannot run plans without Stomp configuration to track progress"
    )


@pytest.mark.stomp
def test_valid_stomp_config_for_listener(runner: CliRunner):
    result = runner.invoke(
        main,
        [
            "-c",
            "tests/example_yaml/valid_stomp_config.yaml",
            "controller",
            "listen",
        ],
        input="\n",
    )
    assert result.exit_code == 0


@pytest.mark.handler
@patch("blueapi.service.handler.Handler")
@patch("requests.request")
def test_get_env(
    mock_requests: Mock,
    mock_handler: Mock,
    handler: Handler,
    client: TestClient,
    runner: CliRunner,
):
    with patch("uvicorn.run", side_effect=None):
        result = runner.invoke(main, ["serve"])

    assert result.exit_code == 0

    mock_requests.return_value = Mock()

    runner.invoke(main, ["controller", "env"])

    assert mock_requests.call_args[0] == (
        "GET",
        "http://localhost:8000/environment",
    )


@pytest.mark.handler
@patch("blueapi.service.handler.Handler")
@patch("blueapi.cli.rest.BlueapiRestClient.get_environment")
@patch("blueapi.cli.rest.BlueapiRestClient.reload_environment")
@patch("blueapi.cli.cli.sleep", return_value=None)
def test_reset_env_client_behavior(
    mock_sleep: MagicMock,
    mock_reload_environment: Mock,
    mock_get_environment: Mock,
    mock_handler: Mock,
    handler: Handler,
    client: TestClient,
    runner: CliRunner,
):
    # Configure the mock_requests to simulate different responses
    # First two calls return not initialized, followed by an initialized response
    mock_get_environment.side_effect = [
        EnvironmentResponse(initialized=False),  # not initialized
        EnvironmentResponse(initialized=False),  # not initialized
        EnvironmentResponse(initialized=True),  # finally initalized
    ]
    mock_reload_environment.return_value = "Environment reload initiated."

    with patch("uvicorn.run", side_effect=None):
        serve_result = runner.invoke(main, ["serve"])

    assert serve_result.exit_code == 0

    # Invoke the CLI command that would trigger the environment initialization check
    reload_result = runner.invoke(main, ["controller", "env", "-r"])

    assert mock_get_environment.call_count == 3

    # Verify if sleep was called between polling iterations
    assert mock_sleep.call_count == 2  # Since the last check doesn't require a sleep

    # Check if the final environment status is printed correctly
    # assert "Environment is initialized." in result.output
    assert (
        reload_result.output
        == "Reloading the environment...\nEnvironment reload initiated.\nWaiting for environment to initialize...\nWaiting for environment to initialize...\nEnvironment is initialized.\ninitialized=True\n"  # noqa: E501
    )


@responses.activate
@pytest.mark.handler
@patch("blueapi.service.handler.Handler")
@patch("blueapi.cli.cli.sleep", return_value=None)
def test_env_endpoint_interaction(
    mock_sleep: MagicMock, mock_handler: Mock, handler: Handler, runner: CliRunner
):
    # Setup mocked responses for the REST endpoints
    responses.add(
        responses.DELETE,
        "http://localhost:8000/environment",
        status=200,
        json=EnvironmentResponse(initialized=False).dict(),
    )
    responses.add(
        responses.GET,
        "http://localhost:8000/environment",
        json=EnvironmentResponse(initialized=False).dict(),
        status=200,
    )
    responses.add(
        responses.GET,
        "http://localhost:8000/environment",
        json=EnvironmentResponse(initialized=False).dict(),
        status=200,
    )
    responses.add(
        responses.GET,
        "http://localhost:8000/environment",
        status=200,
        json=EnvironmentResponse(initialized=True).dict(),
    )

    # Run the command that should interact with these endpoints
    result = runner.invoke(main, ["controller", "env", "-r"])

    # Check if the endpoints were hit as expected
    assert len(responses.calls) == 4  # Ensures that all expected calls were made

    for index, call in enumerate(responses.calls):
        if index == 0:
            assert call.request.method == "DELETE"
            assert call.request.url == "http://localhost:8000/environment"
        else:
            assert call.request.method == "GET"
            assert call.request.url == "http://localhost:8000/environment"

    # Check other assertions as needed, e.g., output or exit codes
    assert result.exit_code == 0
    assert "Environment is initialized." in result.output


@pytest.mark.handler
@responses.activate
@patch("blueapi.service.handler.Handler")
@patch("blueapi.cli.cli.sleep", return_value=None)
def test_env_timeout(
    mock_sleep: MagicMock, mock_handler: Mock, handler: Handler, runner: CliRunner
):
    max_polling_count = 10  # Assuming this is your max polling count in the command

    # Setup mocked responses for the REST endpoints
    responses.add(
        responses.DELETE,
        "http://localhost:8000/environment",
        status=200,
        json=EnvironmentResponse(initialized=False).dict(),
    )
    # Add responses for each polling attempt, all indicating not initialized
    for _ in range(max_polling_count):
        responses.add(
            responses.GET,
            "http://localhost:8000/environment",
            json=EnvironmentResponse(initialized=False).dict(),
            status=200,
        )

    # Run the command that should interact with these endpoints
    result = runner.invoke(main, ["controller", "env", "-r"])
    if result.exception is not None:
        assert isinstance(result.exception, TimeoutError), "Expected a TimeoutError"
        assert result.exception.args[0] == "Environment initialization timed out."
    else:
        raise AssertionError("Expected an exception but got None")

    # Check if the endpoints were hit as expected
    assert len(responses.calls) == max_polling_count + 1  # +1 for the DELETE call

    # First call should be DELETE
    assert responses.calls[0].request.method == "DELETE"
    assert responses.calls[0].request.url == "http://localhost:8000/environment"

    # Remaining calls should all be GET
    for call in responses.calls[1:]:  # Skip the first DELETE request
        assert call.request.method == "GET"
        assert call.request.url == "http://localhost:8000/environment"

    # Check the output for the timeout message
    assert (
        result.exit_code == 1
    )  # Assuming your command exits successfully even on timeout for simplicity


@pytest.mark.handler
@responses.activate
@patch("blueapi.service.handler.Handler")
@patch("blueapi.cli.cli.sleep", return_value=None)
def test_env_reload_server_side_error(
    mock_sleep: MagicMock, mock_handler: Mock, handler: Handler, runner: CliRunner
):
    # Setup mocked error response from the server
    responses.add(
        responses.DELETE,
        "http://localhost:8000/environment",
        status=500,
        json={},
    )
    # Run the command that should interact with these endpoints
    result = runner.invoke(main, ["controller", "env", "-r"])
    if result.exception is not None:
        assert isinstance(
            result.exception, BlueskyRemoteError
        ), "Expected a BlueskyRemoteError"
        assert result.exception.args[0] == "Failed to reload the environment"
    else:
        raise AssertionError("Expected an exception but got None")

    # Check if the endpoints were hit as expected
    assert len(responses.calls) == 1  # +1 for the DELETE call

    # Only call should be DELETE
    assert responses.calls[0].request.method == "DELETE"
    assert responses.calls[0].request.url == "http://localhost:8000/environment"

    # Check the output for the timeout message
    assert (
        result.exit_code == 1
    )  # Assuming your command exits successfully even on timeout for simplicity


@pytest.fixture
def mock_config():
    # Mock configuration setup
    config = {"stomp": MagicMock()}
    rest_client = MagicMock()
    return {"config": config, "rest_client": rest_client}


@pytest.mark.parametrize(
    "exception, expected_exit_code",
    [
        (ValidationError("Invalid parameters", BaseModel), 1),
        (BlueskyRemoteError("Server error"), 1),
        (ValueError("Error parsing parameters"), 1),
    ],
)
def test_error_handling(mock_config, exception, expected_exit_code, runner: CliRunner):
    # Patching the create_task method to raise different exceptions
    with patch("blueapi.cli.rest.BlueapiRestClient.create_task", side_effect=exception):
        result = runner.invoke(
            main,
            [
                "-c",
                "tests/example_yaml/valid_stomp_config.yaml",
                "controller",
                "run",
                "sleep",
                "'{\"time\": 5}'",
            ],
            input="\n",
            obj=mock_config,
        )
        assert result.exit_code == expected_exit_code

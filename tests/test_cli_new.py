from dataclasses import dataclass
from unittest.mock import Mock, patch

import pytest
import responses
from click.testing import CliRunner
from pydantic import BaseModel
from requests.exceptions import ConnectionError
from responses import matchers

from blueapi import __version__
from blueapi.cli.cli import main
from blueapi.core.bluesky_types import Plan
from blueapi.service.model import (
    DeviceModel,
    DeviceResponse,
    EnvironmentResponse,
    PlanModel,
    PlanResponse,
)


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
def test_connection_error_caught_by_wrapper_func(
    mock_requests: Mock, runner: CliRunner
):
    mock_requests.side_effect = ConnectionError()
    result = runner.invoke(main, ["controller", "plans"])

    assert result.stdout == "Failed to establish connection to FastAPI server.\n"


class MyModel(BaseModel):
    id: str


@dataclass
class MyDevice:
    name: str


@responses.activate
def test_get_plans(runner: CliRunner):
    plan = Plan(name="my-plan", model=MyModel)

    response = responses.add(
        responses.GET,
        "http://localhost:8000/plans",
        json=PlanResponse(plans=[PlanModel.from_plan(plan)]).dict(),
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
        json=DeviceResponse(devices=[DeviceModel.from_device(device)]).dict(),
        status=200,
    )

    plans = runner.invoke(main, ["controller", "devices"])
    assert response.call_count == 1
    assert plans.output == "my-device\n    HasName\n"


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

    config_path = "tests/example_yaml/rest_config.yaml"
    runner.invoke(
        main, ["-c", config_path, "controller", "run", "sleep", '{"time": 5}']
    )

    assert response.call_count == 1


def test_invalid_stomp_config_for_listener(runner: CliRunner):
    result = runner.invoke(main, ["controller", "listen"])
    assert isinstance(result.exception, RuntimeError)
    assert str(result.exception) == "Message bus needs to be configured"


def test_cannot_run_plans_without_stomp_config(runner: CliRunner):
    result = runner.invoke(main, ["controller", "run", "sleep", '{"time": 5}'])
    assert result.exit_code == 1
    assert isinstance(result.exception, RuntimeError)
    assert (
        str(result.exception)
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
    assert (
        result.output
        == "Subscribing to all bluesky events from localhost:61613\nPress enter to exit"
    )
    assert result.exit_code == 0


@responses.activate
def test_get_env(
    runner: CliRunner,
):
    response = responses.add(
        responses.GET,
        "http://localhost:8000/environment",
        json=EnvironmentResponse(initialized=True).dict(),
        status=200,
    )

    env = runner.invoke(main, ["controller", "env"])
    assert env.output == "initialized=True error_message=None\n"


@responses.activate(assert_all_requests_are_fired=True)
@patch("blueapi.cli.cli.sleep", return_value=None)
def test_reset_env_client_behavior(
    mock_sleep: Mock,
    runner: CliRunner,
):
    responses.add(
        responses.DELETE,
        "http://localhost:8000/environment",
        json=EnvironmentResponse(initialized=False).dict(),
        status=200,
    )

    env_state = [False, False, True]

    for state in env_state:
        responses.add(
            responses.GET,
            "http://localhost:8000/environment",
            json=EnvironmentResponse(initialized=state).dict(),
            status=200,
        )

    # Invoke the CLI command that would trigger the environment initialization check
    reload_result = runner.invoke(main, ["controller", "env", "-r"])

    # Verify if sleep was called between polling iterations
    assert mock_sleep.call_count == 2  # Since the last check doesn't require a sleep

    for index, call in enumerate(responses.calls):
        if index == 0:
            assert call.request.method == "DELETE"
            assert call.request.url == "http://localhost:8000/environment"
        else:
            assert call.request.method == "GET"
            assert call.request.url == "http://localhost:8000/environment"

    # Check if the final environment status is printed correctly
    # assert "Environment is initialized." in result.output
    assert (
        reload_result.output
        == """Reloading the environment...
initialized=False error_message=None
Waiting for environment to initialize...
Waiting for environment to initialize...
Environment is initialized.
initialized=True error_message=None
"""
    )


@responses.activate
@patch("blueapi.cli.cli.sleep", return_value=None)
def test_env_timeout(
    mock_sleep: Mock,   runner: CliRunner
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
    assert result.output == "Reloading the environment...\ninitialized=False error_message=None\n" + "Waiting for environment to initialize...\n"*10
    assert (
        result.exit_code == 1
    )  # Assuming your command exits successfully even on timeout for simplicity


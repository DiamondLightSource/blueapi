from dataclasses import dataclass
from unittest.mock import call

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient
from mock import Mock, patch
from pydantic import BaseModel
from requests.exceptions import ConnectionError

from blueapi import __version__
from blueapi.cli.cli import main
from blueapi.core.bluesky_types import Plan
from blueapi.service.handler import Handler, teardown_handler


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


def test_main_with_nonexistent_config_file():
    runner = CliRunner()
    result = runner.invoke(main, ["-c", "tests/non_existent.yaml"])

    result.exit_code == 1
    type(result.exception) is FileNotFoundError


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
    config_path = "tests/example_yaml/rest_config.yaml"

    mock_handler.side_effect = Mock(return_value=handler)
    with patch("uvicorn.run", side_effect=None):
        result = runner.invoke(main, ["-c", config_path, "serve"])
        assert result.exit_code == 0

    assert result.exit_code == 0

    # Put a plan in handler.context manually.
    plan = Plan(name="my-plan", model=MyModel)
    handler._context.plans = {"my-plan": plan}

    # Setup requests.get call to return the output of the FastAPI call for plans.
    # Call the CLI function and check the output.
    _ = runner.invoke(main, ["-c", config_path, "controller", "plans"])

    assert mock_requests.call_args_list[0] == call(
        "GET",
        "http://a.fake.host:12345/plans",
        json=None,
    )


@pytest.mark.handler
@patch("blueapi.service.handler.Handler")
@patch("requests.request")
def test_plan_accepted_with_right_parameters(
    mock_requests: Mock,
    mock_handler: Mock,
    handler: Handler,
    client: TestClient,
    runner: CliRunner,
):

    # needed so that the handler is instantiated as MockHandler() instead of Handler().
    mock_handler.side_effect = Mock(return_value=handler)

    # Setup the (Mock)Handler.
    with patch("uvicorn.run", side_effect=None):
        result = runner.invoke(main, ["serve"])

    assert result.exit_code == 0

    mock_requests.return_value = client.get("/plans/sleep")
    output = runner.invoke(main, ["controller", "run", "sleep", '{"time": 5}'])
    assert result.exit_code == 0
    print(output)

    # expect the first call to be to the helper
    assert mock_requests.call_args_list[0] == call(
        "GET", "http://localhost:8000/plans/sleep", json=None
    )

    mock_requests.return_value = client.post(
        "/tasks", json={"name": "sleep", "params": {"time": 5}}
    )
    assert len(mock_requests.call_args_list) == 2

    assert mock_requests.call_args_list[1] == call(
        "POST",
        "http://localhost:8000/tasks",
        json={"name": "sleep", "params": {"time": 5}},
    )


@pytest.mark.handler
@patch("blueapi.service.handler.Handler")
@patch("requests.request")
def test_plan_rejected_with_wrong_parameters(
    mock_requests: Mock,
    mock_handler: Mock,
    handler: Handler,
    client: TestClient,
    runner: CliRunner,
):

    # needed so that the handler is instantiated as MockHandler() instead of Handler().
    mock_handler.side_effect = Mock(return_value=handler)

    # Setup the (Mock)Handler.
    with patch("uvicorn.run", side_effect=None):
        result = runner.invoke(main, ["serve"])

    assert result.exit_code == 0

    mock_requests.return_value = client.get("/plans/sleep")
    # Erroneous invocation - with a string argument instead of number
    output = runner.invoke(main, ["controller", "run", "sleep", '{"tim": "test"}'])
    assert result.exit_code == 0
    print(output)

    # expect the first and only call to be to the helper
    assert mock_requests.call_args_list[0] == call(
        "GET", "http://localhost:8000/plans/sleep", json=None
    )

    assert len(mock_requests.call_args_list) == 1

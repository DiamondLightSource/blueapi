import json
from collections.abc import Mapping
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from textwrap import dedent
from unittest.mock import Mock, patch

import pytest
import responses
from click.testing import CliRunner
from pydantic import BaseModel, ValidationError
from requests.exceptions import ConnectionError
from responses import matchers

from blueapi import __version__
from blueapi.cli.cli import main
from blueapi.cli.format import OutputFormat
from blueapi.client.rest import BlueskyRemoteControlError
from blueapi.config import ScratchConfig, ScratchRepository
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
    responses.add(
        responses.GET,
        "http://localhost:8000/environment",
        json=EnvironmentResponse(initialized=True).dict(),
        status=200,
    )

    env = runner.invoke(main, ["controller", "env"])
    assert env.output == "initialized=True error_message=None\n"


@responses.activate(assert_all_requests_are_fired=True)
@patch("blueapi.client.client.time.sleep", return_value=None)
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
    assert reload_result.output == dedent("""\
                Reloading environment
                Environment is initialized
                initialized=True error_message=None
                """)


@responses.activate
@patch("blueapi.client.client.time.sleep", return_value=None)
def test_env_timeout(mock_sleep: Mock, runner: CliRunner):
    # Setup mocked responses for the REST endpoints
    responses.add(
        responses.DELETE,
        "http://localhost:8000/environment",
        status=200,
        json=EnvironmentResponse(initialized=False).dict(),
    )
    # Add responses for each polling attempt, all indicating not initialized
    responses.add(
        responses.GET,
        "http://localhost:8000/environment",
        json=EnvironmentResponse(initialized=False).dict(),
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
    for call in responses.calls[1:]:  # Skip the first DELETE request
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
    assert isinstance(
        result.exception, BlueskyRemoteControlError
    ), "Expected a BlueskyRemoteError from cli runner"
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
    "exception, expected_exit_code",
    [
        (ValidationError("Invalid parameters", BaseModel), 1),
        (BlueskyRemoteControlError("Server error"), 1),
        (ValueError("Error parsing parameters"), 1),
    ],
)
def test_error_handling(exception, expected_exit_code, runner: CliRunner):
    # Patching the create_task method to raise different exceptions
    with patch(
        "blueapi.client.rest.BlueapiRestClient.create_task", side_effect=exception
    ):
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
        )
        assert result.exit_code == expected_exit_code


def test_device_output_formatting():
    """Test for alternative device output formats"""

    device = MyDevice("my-device")

    devices = DeviceResponse(devices=[DeviceModel.from_device(device)])

    compact = dedent("""\
                my-device
                    HasName
                """)

    output = StringIO()
    OutputFormat.COMPACT.display(devices, out=output)
    assert output.getvalue() == compact

    # json outputs valid json
    output = StringIO()
    OutputFormat.JSON.display(devices, out=output)
    json_out = dedent("""\
                [
                  {
                    "name": "my-device",
                    "protocols": [
                      "HasName"
                    ]
                  }
                ]
                """)
    assert output.getvalue() == json_out
    _ = json.loads(output.getvalue())

    output = StringIO()
    OutputFormat.FULL.display(devices, out=output)
    full = dedent("""\
            my-device
                HasName
            """)
    assert output.getvalue() == full


class ExtendedModel(BaseModel):
    name: str
    keys: list[int]
    metadata: None | Mapping[str, str]


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

    output = StringIO()
    OutputFormat.COMPACT.display(plans, out=output)
    assert output.getvalue() == compact

    # json outputs valid json
    output = StringIO()
    OutputFormat.JSON.display(plans, out=output)
    json_out = dedent("""\
                [
                  {
                    "name": "my-plan",
                    "description": "Summary of description\\n\\nRest of description\\n",
                    "parameter_schema": {
                      "title": "ExtendedModel",
                      "type": "object",
                      "properties": {
                        "name": {
                          "title": "Name",
                          "type": "string"
                        },
                        "keys": {
                          "title": "Keys",
                          "type": "array",
                          "items": {
                            "type": "integer"
                          }
                        },
                        "metadata": {
                          "title": "Metadata",
                          "type": "object",
                          "additionalProperties": {
                            "type": "string"
                          }
                        }
                      },
                      "required": [
                        "name",
                        "keys"
                      ]
                    }
                  }
                ]
                """)
    assert output.getvalue() == json_out
    _ = json.loads(output.getvalue())

    output = StringIO()
    OutputFormat.FULL.display(plans, out=output)
    full = dedent("""\
            my-plan
                Summary of description

                Rest of description
                Schema
                    {
                      "title": "ExtendedModel",
                      "type": "object",
                      "properties": {
                        "name": {
                          "title": "Name",
                          "type": "string"
                        },
                        "keys": {
                          "title": "Keys",
                          "type": "array",
                          "items": {
                            "type": "integer"
                          }
                        },
                        "metadata": {
                          "title": "Metadata",
                          "type": "object",
                          "additionalProperties": {
                            "type": "string"
                          }
                        }
                      },
                      "required": [
                        "name",
                        "keys"
                      ]
                    }
            """)
    assert output.getvalue() == full


def test_unknown_object_formatting():
    demo = {"foo": 42, "bar": ["hello", "World"]}

    output = StringIO()
    OutputFormat.JSON.display(demo, output)
    exp = """{"foo": 42, "bar": ["hello", "World"]}\n"""
    assert exp == output.getvalue()

    output = StringIO()
    OutputFormat.COMPACT.display(demo, output)
    exp = """{'bar': ['hello', 'World'], 'foo': 42}\n"""
    assert exp == output.getvalue()

    output = StringIO()
    OutputFormat.FULL.display(demo, output)
    assert exp == output.getvalue()


def test_generic_base_model_formatting():
    output = StringIO()
    obj = ExtendedModel(name="foo", keys=[1, 2, 3], metadata={"fizz": "buzz"})
    exp = dedent("""\
            {
              "name": "foo",
              "keys": [
                1,
                2,
                3
              ],
              "metadata": {
                "fizz": "buzz"
              }
            }
            """)
    OutputFormat.JSON.display(obj, output)
    assert exp == output.getvalue()


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
        ["-c", "tests/example_yaml/scratch.yaml", "setup-scratch"],
        input="\n",
    )
    assert result.exit_code == 0
    mock_setup_scratch.assert_called_once_with(expected_config)

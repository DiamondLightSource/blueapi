import json
from dataclasses import dataclass
from unittest.mock import MagicMock, Mock, patch

import pytest
from click.testing import CliRunner
from dodal.devices.scatterguard import Scatterguard
from pydantic import BaseModel

from blueapi import __version__
from blueapi.cli.cli_new import main
from blueapi.core.bluesky_types import Plan
from blueapi.openapi_client.models.plan_response import PlanResponse
from blueapi.openapi_client.models.task_response import TaskResponse
from blueapi.service.handler import teardown_handler
from blueapi.service.model import DeviceModel, DeviceResponse, PlanModel


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

    assert result.exit_code == 1
    assert type(result.exception) is FileNotFoundError


class MyModel(BaseModel):
    id: str


@dataclass
class MyDevice:
    name: str


def test_invalid_config_path_handling(runner: CliRunner):
    # test what happens if you pass an invalid config file...
    result = runner.invoke(main, ["-c", "non_existent.yaml"])
    assert result.exit_code == 1


def test_invalid_stomp_config_for_listener(runner: CliRunner):
    result = runner.invoke(main, ["controller", "listen"])
    assert (
        isinstance(result.exception, RuntimeError)
        and str(result.exception) == "Message bus needs to be configured"
    )


def test_cannot_run_plans_without_stomp_config(runner: CliRunner):
    result = runner.invoke(main, ["controller", "run", "sleep", '{"time": 5}'])
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


def test_invalid_condition_for_run(runner: CliRunner):
    result = runner.invoke(main, ["controller", "run", "sleep", '{"time": 5}'])
    assert type(result.exception) is RuntimeError


@patch("urllib3.PoolManager.request")
def test_get_devices_empty_with_custom_config(mock_requests: Mock, runner: CliRunner):
    # Setup a mock response
    mock_urllib3_response = MagicMock()
    mock_urllib3_response.status = 200
    mock_urllib3_response.reason = "OK"
    mock_urllib3_response.data = b'{"devices": []}'
    mock_urllib3_response.headers = {"Content-Type": "application/json"}

    config_path = "tests/example_yaml/rest_config.yaml"

    with patch("uvicorn.run", side_effect=None):
        initial_result = runner.invoke(main, ["-c", config_path, "serve"])
        print(initial_result)

    # Configure the mock to return the response
    mock_requests.return_value = mock_urllib3_response

    response = runner.invoke(main, ["-c", config_path, "controller", "devices"])
    mock_requests.assert_called_once_with(
        "GET",
        "http://a.fake.host:12345/devices",
        fields={},
        preload_content=True,
        timeout=None,
        headers={
            "Accept": "application/json",
            "User-Agent": "OpenAPI-Generator/1.0.0/python",
        },
    )
    assert response.exit_code == 0
    assert response.output == "{'devices': []}\n"


@patch("urllib3.PoolManager.request")
def test_get_devices_with_one_device(mock_requests: Mock, runner: CliRunner):
    # Setup a mock response
    mock_urllib3_response = MagicMock()
    mock_urllib3_response.status = 200
    mock_urllib3_response.reason = "OK"
    sg = Scatterguard(name="my-scatterguard")
    sg_model = DeviceModel.from_device(sg)
    r = DeviceResponse(devices=[sg_model])

    expected_dict = r.json()
    mock_urllib3_response.data = expected_dict.encode()
    mock_urllib3_response.headers = {"Content-Type": "application/json"}

    config_path = "tests/example_yaml/rest_config.yaml"

    with patch("uvicorn.run", side_effect=None):
        initial_result = runner.invoke(main, ["-c", config_path, "serve"])
        print(initial_result)

    # Configure the mock to return the response
    mock_requests.return_value = mock_urllib3_response

    response = runner.invoke(main, ["-c", config_path, "controller", "devices"])
    mock_requests.assert_called_once_with(
        "GET",
        "http://a.fake.host:12345/devices",
        fields={},
        preload_content=True,
        timeout=None,
        headers={
            "Accept": "application/json",
            "User-Agent": "OpenAPI-Generator/1.0.0/python",
        },
    )
    assert response.exit_code == 0
    parsed_response = json.loads(
        response.output.replace("'", '"')
    )  # Replace single quotes to double quotes for valid JSON format
    parsed_expected = json.loads(expected_dict)
    assert parsed_response == parsed_expected


@patch("urllib3.PoolManager.request")
def test_get_plans_empty(mock_requests: Mock, runner: CliRunner):
    # Setup a mock response
    mock_urllib3_response = MagicMock()
    mock_urllib3_response.status = 200
    mock_urllib3_response.reason = "OK"
    r = PlanResponse(plans=[])
    expected_dict = r.json()
    mock_urllib3_response.data = expected_dict.encode()
    mock_urllib3_response.headers = {"Content-Type": "application/json"}

    mock_requests.return_value = mock_urllib3_response

    config_path = "tests/example_yaml/rest_config.yaml"

    with patch("uvicorn.run", side_effect=None):
        initial_result = runner.invoke(main, ["-c", config_path, "serve"])
        print(initial_result)

    # Configure the mock to return the response
    response = runner.invoke(main, ["-c", config_path, "controller", "plans"])

    mock_requests.assert_called_once_with(
        "GET",
        "http://a.fake.host:12345/plans",
        fields={},
        preload_content=True,
        timeout=None,
        headers={
            "Accept": "application/json",
            "User-Agent": "OpenAPI-Generator/1.0.0/python",
        },
    )

    parsed_response = json.loads(
        response.output.replace("'", '"')
    )  # Replace single quotes to double quotes for valid JSON format
    parsed_expected = json.loads(expected_dict)
    assert parsed_response == parsed_expected


@patch("urllib3.PoolManager.request")
def test_get_plans_one_plan(mock_requests: Mock, runner: CliRunner):
    sleep_plan = Plan(
        model=PlanModel,
        name="todo",
        description="just a description",
    )

    sleep_model = PlanModel.from_plan(sleep_plan)
    # Setup a mock response
    mock_urllib3_response = MagicMock()
    mock_urllib3_response.status = 200
    mock_urllib3_response.reason = "OK"
    r = PlanResponse(plans=[sleep_model])
    expected_dict = r.json()
    mock_urllib3_response.data = expected_dict.encode()
    mock_urllib3_response.headers = {"Content-Type": "application/json"}

    mock_requests.return_value = mock_urllib3_response

    config_path = "tests/example_yaml/rest_config.yaml"

    with patch("uvicorn.run", side_effect=None):
        initial_result = runner.invoke(main, ["-c", config_path, "serve"])
        print(initial_result)

    # Configure the mock to return the response
    response = runner.invoke(main, ["-c", config_path, "controller", "plans"])

    mock_requests.assert_called_once_with(
        "GET",
        "http://a.fake.host:12345/plans",
        fields={},
        preload_content=True,
        timeout=None,
        headers={
            "Accept": "application/json",
            "User-Agent": "OpenAPI-Generator/1.0.0/python",
        },
    )

    p = response.output.replace("'", '"').replace(
        "None", "null"
    )  # NOTE that is a bit odd maybe pydantic serializer will be diff later
    parsed_expected = json.loads(expected_dict)
    parsed_response = json.loads(p)
    assert parsed_response == parsed_expected


@patch("urllib3.PoolManager.request")
def test_handle_sleep_plan_accepted(mock_requests: Mock, runner: CliRunner):
    # Setup a mock response
    mock_urllib3_response = MagicMock()
    mock_urllib3_response.status = 201
    mock_urllib3_response.reason = "OK"
    r = TaskResponse(task_id="123")
    expected_dict = r.json()
    mock_urllib3_response.data = expected_dict.encode()
    mock_urllib3_response.headers = {"Content-Type": "application/json"}

    mock_requests.return_value = mock_urllib3_response

    config_path = "tests/example_yaml/rest_config.yaml"

    with patch("uvicorn.run", side_effect=None):
        initial_result = runner.invoke(main, ["-c", config_path, "serve"])
        print(initial_result)

    response = runner.invoke(
        main, ["-c", config_path, "controller", "run", "sleep", '{"time": 5}']
    )

    mock_requests.assert_called_once_with(
        "POST",
        "http://a.fake.host:12345/tasks",
        fields={},
        preload_content=True,
        timeout=None,
        headers={
            "Accept": "application/json",
            "User-Agent": "OpenAPI-Generator/1.0.0/python",
        },
    )

    p = response.output.replace("'", '"').replace(
        "None", "null"
    )  # NOTE that is a bit odd maybe pydantic serializer will be diff later
    parsed_expected = json.loads(expected_dict)
    parsed_response = json.loads(p)
    assert parsed_response == parsed_expected


@patch("urllib3.PoolManager.request")
def test_handle_sleep_plan_rejected(mock_requests: Mock, runner: CliRunner):
    raise AssertionError("Not implemented")
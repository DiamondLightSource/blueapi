from dataclasses import dataclass
from unittest.mock import MagicMock, Mock, patch

import pytest
from click.testing import CliRunner
from dodal.devices.scatterguard import Scatterguard
from pydantic import BaseModel

from blueapi import __version__
from blueapi.cli.cli_new import main
from blueapi.core.bluesky_types import Plan
from blueapi.openapi_client.models.device_model import DeviceModel
from blueapi.openapi_client.rest import RESTResponse
from blueapi.service.handler import teardown_handler


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


@pytest.mark.handler
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


@pytest.mark.handler
@patch("urllib3.PoolManager.request")
def test_get_devices_with_one_device(mock_requests: Mock, runner: CliRunner):
    # Setup a mock response
    mock_urllib3_response = MagicMock()
    mock_urllib3_response.status = 200
    mock_urllib3_response.reason = "OK"
    sg = Scatterguard(name="my-scatterguard")
    model = DeviceModel.from_device(sg)
    raw_response = f'{"devices": [{model}]}'
    mock_urllib3_response.data = raw_response.encode()
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
    assert response.output == f"{raw_response}\n"


@pytest.mark.handler
@patch("blueapi.service.handler.Handler")
@patch("urllib3.PoolManager.request")
def test_get_plans_empty(mock_requests: Mock, mock_handler: Mock, runner: CliRunner):
    # Setup a mock response
    # resp = {"status": 200, "data": b'{"plans": []}', "reason": "OK"}
    mock_urllib3_response = MagicMock()
    mock_urllib3_response.status = 200
    mock_urllib3_response.reason = "OK"
    mock_urllib3_response.data = b'{"plans": []}'
    mock_urllib3_response.headers = {"Content-Type": "application/json"}

    # Create RESTResponse instance using the mocked urllib3 response
    mock_response = RESTResponse(resp=mock_urllib3_response)
    # mock_response = RESTResponse(resp=resp)

    # Put a plan in handler.context manually.

    config_path = "tests/example_yaml/rest_config.yaml"

    with patch("uvicorn.run", side_effect=None):
        initial_result = runner.invoke(main, ["-c", config_path, "serve"])
        print(initial_result)

    # Configure the mock to return the response
    mock_requests.return_value = mock_response

    plan = Plan(name="my-plan", model=MyModel)
    mock_handler._context.plans = {"my-plan": plan}
    plans = runner.invoke(main, ["-c", config_path, "controller", "plans"])
    # ValueError('stderr not separately captured')
    # (<class 'TypeError'>,
    # TypeError("expected string or bytes-like object, got 'MagicMock'")
    # response = plan.json()

    assert (
        plans.output == "{'plans': [{'description': None,\n"
        "            'name': 'my-plan',\n"
        "            'parameter_schema': {'properties': {'id': {'title': 'Id',\n"
        "                                                       'type': 'string'}},\n"
        "                                 'required': ['id'],\n"
        "                                 'title': 'MyModel',\n"
        "                                 'type': 'object'}}]}\n"
    )

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
    # todo set plan with sleep args
    # runner.invoke(
    #     main, ["-c", config_path, "controller", "run", "sleep", '{"time": 5}']
    # )

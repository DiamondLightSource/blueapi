from dataclasses import dataclass
from unittest.mock import Mock, patch

import pytest
import requests
import responses
from click.testing import CliRunner
from pydantic import BaseModel
from responses import matchers

from blueapi import __version__
from blueapi.cli.cli import main
from blueapi.core.bluesky_types import Plan
from blueapi.service.model import DeviceModel, DeviceResponse, PlanModel, PlanResponse


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
        match=matchers.json_params_matcher(body_data, strict_match=False),
        content_type="application/json",
    )

    config_path = "tests/example_yaml/rest_config.yaml"
    runner.invoke(
        main, ["-c", config_path, "controller", "run", "sleep", '{"time": 5}']
    )

    assert response.call_count == 1


@responses.activate
def test_nau():
    r = responses.post(
        url="http://example.com/",
        body="one",
        match=[
            matchers.json_params_matcher({"page": {"name": "first", "type": "json"}})
        ],
    )
    resp = requests.request(
        "POST",
        "http://example.com/",
        headers={"Content-Type": "application/json"},
        json={"page": {"name": "first", "type": "json"}},
    )

    assert r.call_count == 2

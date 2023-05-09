from dataclasses import dataclass

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient
from mock import Mock, patch
from pydantic import BaseModel

from blueapi import __version__
from blueapi.cli.cli import main
from blueapi.core.bluesky_types import Plan
from blueapi.core.context import BlueskyContext
from blueapi.service.handler import get_handler
from blueapi.service.main import app
from blueapi.worker.reworker import RunEngineWorker
from blueapi.worker.task import ActiveTask


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
    type(result.exception) == FileNotFoundError


def test_controller_plans():
    runner = CliRunner()
    result = runner.invoke(main, ["controller", "plans"])

    assert result.stdout == "Failed to establish connection to FastAPI server.\n"


# Some CLI commands require the rest api to be running...


class MockHandler:
    context: BlueskyContext
    worker: RunEngineWorker

    def __init__(self) -> None:
        self.context = BlueskyContext()
        self.worker = RunEngineWorker(self.context)

    def start(self):
        return None


class Client:
    def __init__(self, handler: MockHandler) -> None:
        """Create tester object"""
        self.handler = handler

    @property
    def client(self) -> TestClient:
        app.dependency_overrides[get_handler] = lambda: self.handler
        return TestClient(app)


class MyModel(BaseModel):
    id: str


@dataclass
class MyDevice:
    name: str


@patch("blueapi.service.handler.Handler", autospec=True)
@patch("uvicorn.run", side_effect=[None])
def test_deprecated_worker_command(mock_handler, mock_uvicorn, runner: CliRunner):
    dummy = Mock()
    dummy.return_value = MockHandler()
    mock_handler.side_effect = [dummy]

    result = runner.invoke(main, ["worker"])

    assert result.output == (
        "DeprecationWarning: The command 'worker' is deprecated.\n"
        + "Please use run command instead.\n\n"
    )


@patch("blueapi.service.handler.Handler")
@patch("requests.get")
def test_get_plans_and_devices(mock_requests, mock_handler, runner: CliRunner):
    """Integration test which attempts to test a couple of CLI commands.

    This test mocks out the handler so that setup_handler (which gets called at the
    start of the application when the CLI command `blueapi run` is executed) actually
    sets up a handler I can directly add things to, e.g. plans and devices.
    In reality, at this stage the bluesky worker would be started and a connection
    to activemq setup. However, the mocked handler does not do this for simplicity's
    sake.

    This test also mocks out the calls to rest API endpoints with calls to a
    TestClient instance for FastAPI.

    The CliRunner fixture passed to this test simply runs the CLI commands passed to
    it.
    """

    handler = MockHandler()

    dummy = Mock()
    dummy.return_value = handler
    mock_handler.side_effect = [dummy]

    with patch("uvicorn.run", side_effect=[None]):
        result = runner.invoke(main, ["serve"])

    assert result.exit_code == 0

    plan = Plan(name="my-plan", model=MyModel)
    handler.context.plans = {"my-plan": plan}
    mock_requests.return_value = Client(handler).client.get("/plans")
    plans = runner.invoke(main, ["controller", "plans"])

    assert plans.output == (
        "Response returned with 200: \n{'plans': [{'name': 'my-plan'}]}\n"
    )

    mock_requests.return_value = Client(handler).client.get("/devices")
    unset_devices = runner.invoke(main, ["controller", "devices"])
    assert unset_devices.output == "Response returned with 200: \n{'devices': []}\n"

    device = MyDevice("my-device")
    handler.context.devices = {"my-device": device}
    mock_requests.return_value = Client(handler).client.get("/devices")
    devices = runner.invoke(main, ["controller", "devices"])

    assert devices.output == (
        "Response returned with 200: "
        + "\n{'devices': [{'name': 'my-device', 'protocols': ['HasName']}]}\n"
    )


@patch("blueapi.service.handler.Handler")
@patch("requests.get")
def test_run_plan_through_cli(mock_requests, mock_handler, runner: CliRunner):
    """Integration test which attempts to put a plan on the worker queue.

    This test mocks out the handler so that setup_handler (which gets called at the
    start of the application when the CLI command `blueapi run` is executed) actually
    sets up a handler I can directly add things to, e.g. plans and devices.
    In reality, at this stage the bluesky worker would be started and a connection
    to activemq setup. However, the mocked handler does not do this for simplicity's
    sake.

    This test also mocks out the calls to rest API endpoints with calls to a
    TestClient instance for FastAPI.

    The CliRunner fixture passed to this test simply runs the CLI commands passed to
    it.
    """

    handler = MockHandler()

    dummy = Mock()
    dummy.return_value = handler
    mock_handler.side_effect = [dummy]

    with patch("uvicorn.run", side_effect=[None]):
        result = runner.invoke(main, ["serve"])

    assert result.exit_code == 0

    mock_requests.return_value = Client(handler).client.put(
        "/task/my-task", json={"name": "count", "params": {"detectors": ["x"]}}
    )
    next_task: ActiveTask = handler.worker._task_queue.get(timeout=1.0)

    assert next_task

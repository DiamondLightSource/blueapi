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
def test_get_plans(mock_requests, mock_handler, runner: CliRunner):
    # 1. "start" the server as above... (not really started as uvicorn not run,
    #   but handler set.)
    # 2. add something manually onto the handler and check if you can get it
    #   via the cli. Mock out requests.get with TestClient calls.

    handler = MockHandler()

    dummy = Mock()
    dummy.return_value = handler
    mock_handler.side_effect = [dummy]

    with patch("uvicorn.run", side_effect=[None]):
        result = runner.invoke(main, ["run"])

    assert result.exit_code == 0

    class MyModel(BaseModel):
        id: str

    plan = Plan(name="my-plan", model=MyModel)

    handler.context.plans = {"my-plan": plan}

    mock_requests.return_value = Client(handler).client.get("/plans")

    plans = runner.invoke(main, ["controller", "plans"])
    assert plans.output == (
        "Response returned with 200: " + "\n{'plans': [{'name': 'my-plan'}]}\n"
    )

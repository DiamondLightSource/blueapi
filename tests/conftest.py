# Based on https://docs.pytest.org/en/latest/example/simple.html#control-skipping-of-tests-according-to-command-line-option  # noqa: E501
from typing import Iterator
from unittest.mock import MagicMock

import pytest
from bluesky.run_engine import RunEngineStateMachine
from fastapi.testclient import TestClient

from blueapi.config import EnvironmentConfig
from blueapi.service.controller import BlueskyController, get_controller
from blueapi.service.main import app
from blueapi.worker import RunEngineWorker
from src.blueapi.core import BlueskyContext


def pytest_addoption(parser):
    parser.addoption(
        "--skip-stomp",
        action="store_true",
        default=False,
        help="skip stomp tests (e.g. because a server is unavailable)",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "stomp: mark test as requiring stomp broker")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--skip-stomp"):
        skip_stomp = pytest.mark.skip(reason="skipping stomp tests at user request")
        for item in items:
            if "stomp" in item.keywords:
                item.add_marker(skip_stomp)


class Client:
    def __init__(self, controller: BlueskyController) -> None:
        """Create tester object"""
        self.controller = controller

    @property
    def client(self) -> TestClient:
        app.dependency_overrides[get_controller] = lambda: self.controller
        return TestClient(app)


@pytest.fixture
def controller() -> Iterator[BlueskyController]:
    context: BlueskyContext = BlueskyContext(run_engine=MagicMock())
    context.run_engine.state = RunEngineStateMachine.States.IDLE
    context.with_config(EnvironmentConfig())
    controller = BlueskyController(
        context=context,
        worker=RunEngineWorker(context),
        messaging_template=MagicMock(),
    )

    yield controller
    controller.stop()


@pytest.fixture
def client(controller: BlueskyController) -> TestClient:
    return Client(controller).client

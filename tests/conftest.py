# Based on https://docs.pytest.org/en/latest/example/simple.html#control-skipping-of-tests-according-to-command-line-option  # noqa: E501
from typing import Iterator
from unittest.mock import MagicMock

import pytest
from bluesky.run_engine import RunEngineStateMachine
from fastapi.testclient import TestClient

from blueapi.service.handler import Handler, get_handler
from blueapi.service.main import app
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
    def __init__(self, handler: Handler) -> None:
        """Create tester object"""
        self.handler = handler

    @property
    def client(self) -> TestClient:
        app.dependency_overrides[get_handler] = lambda: self.handler
        return TestClient(app)


@pytest.fixture
def handler() -> Iterator[Handler]:
    context: BlueskyContext = BlueskyContext(run_engine=MagicMock())
    context.run_engine.state = RunEngineStateMachine.States.IDLE
    handler = Handler(context=context, messaging_template=MagicMock())

    yield handler
    handler.stop()


@pytest.fixture
def client(handler: Handler) -> TestClient:
    return Client(handler).client

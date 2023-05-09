# Based on https://docs.pytest.org/en/latest/example/simple.html#control-skipping-of-tests-according-to-command-line-option  # noqa: E501

import pytest
from fastapi.testclient import TestClient
from mock import Mock

from blueapi.core.context import BlueskyContext
from blueapi.service.handler import Handler, get_handler
from blueapi.service.main import app
from blueapi.worker.reworker import RunEngineWorker


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


class MockHandler(Handler):
    context: BlueskyContext
    worker: RunEngineWorker

    def __init__(self) -> None:
        self.context = Mock()
        self.worker = Mock()

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


@pytest.fixture(scope="session")
def handler() -> MockHandler:
    return MockHandler()


@pytest.fixture(scope="session")
def client(handler: MockHandler) -> TestClient:
    return Client(handler).client

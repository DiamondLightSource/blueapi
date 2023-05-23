# Based on https://docs.pytest.org/en/latest/example/simple.html#control-skipping-of-tests-according-to-command-line-option  # noqa: E501

import pytest
from bluesky.run_engine import RunEngineStateMachine
from fastapi.testclient import TestClient
from mock import Mock

from blueapi.service.handler import Handler, get_handler
from blueapi.service.main import app
from src.blueapi.core import BlueskyContext

_TIMEOUT = 10.0


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


@pytest.fixture(scope="session")
def handler() -> Handler:
    context: BlueskyContext = Mock()
    context.run_engine.state = RunEngineStateMachine.States.IDLE
    handler = Handler(context=context)

    def no_op():
        return

    handler.start = handler.stop = no_op  # type: ignore
    return handler


@pytest.fixture(scope="session")
def client(handler: Handler) -> TestClient:
    return Client(handler).client


@pytest.fixture(scope="session")
def timeout() -> float:
    return _TIMEOUT

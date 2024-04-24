import asyncio

# Based on https://docs.pytest.org/en/latest/example/simple.html#control-skipping-of-tests-according-to-command-line-option  # noqa: E501
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from bluesky import RunEngine
from bluesky.run_engine import RunEngineStateMachine, TransitionError
from fastapi.testclient import TestClient

from blueapi.core import BlueskyContext
from blueapi.service.handler import Handler
from blueapi.service.main import app, get_handler


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


@pytest.fixture(scope="function")
def RE(request):
    loop = asyncio.new_event_loop()
    loop.set_debug(True)
    RE = RunEngine({}, call_returns_result=True, loop=loop)

    def clean_event_loop():
        if RE.state not in ("idle", "panicked"):
            try:
                RE.halt()
            except TransitionError:
                pass
        loop.call_soon_threadsafe(loop.stop)
        RE._th.join()
        loop.close()

    request.addfinalizer(clean_event_loop)
    return RE


@pytest.fixture
def handler(RE: RunEngine) -> Iterator[Handler]:
    context: BlueskyContext = BlueskyContext(run_engine=MagicMock())
    context.run_engine.state = RunEngineStateMachine.States.IDLE  # type: ignore
    handler = Handler(context=context, messaging_template=MagicMock())

    yield handler
    handler.stop()


@pytest.fixture
def client(handler: Handler) -> TestClient:
    return Client(handler).client

import asyncio

# Based on https://docs.pytest.org/en/latest/example/simple.html#control-skipping-of-tests-according-to-command-line-option  # noqa: E501
import pytest
from bluesky import RunEngine
from bluesky.run_engine import TransitionError


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

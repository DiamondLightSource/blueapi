# Based on https://docs.pytest.org/en/latest/example/simple.html#control-skipping-of-tests-according-to-command-line-option  # noqa: E501

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--skip-stomp",
        action="store_true",
        default=False,
        help="skip stomp tests (e.g. because a server is unavailable)",
    )
    parser.addoption(
        "--skip-amqp",
        action="store_true",
        default=False,
        help="skip amqp tests (e.g. because no broker is available)",
    )
    parser.addoption(
        "--skip-messaging",
        action="store_true",
        default=False,
        help="skip message broker tests (i.e. stomp + amqp tests)",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "stomp: mark test as requiring stomp broker")
    config.addinivalue_line("markers", "amqp: mark test as requiring amqp broker")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--skip-stomp") or config.getoption("--skip-messaging"):
        skip_stomp = pytest.mark.skip(reason="skipping stomp tests at user request")
        for item in items:
            if "stomp" in item.keywords:
                item.add_marker(skip_stomp)
    if config.getoption("--skip-amqp") or config.getoption("--skip-messaging"):
        skip_amqp = pytest.mark.skip(reason="skipping amqp tests at user request")
        for item in items:
            if "amqp" in item.keywords:
                item.add_marker(skip_amqp)

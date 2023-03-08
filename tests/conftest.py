# Based on https://docs.pytest.org/en/latest/example/simple.html#control-skipping-of-tests-according-to-command-line-option  # noqa: E501

import pytest


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

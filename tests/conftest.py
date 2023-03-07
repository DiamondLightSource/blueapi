# Based on https://docs.pytest.org/en/latest/example/simple.html#control-skipping-of-tests-according-to-command-line-option  # noqa: E501

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--stomp", action="store_true", default=False, help="run stomp tests"
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "stomp: mark test as slow to run")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--stomp"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_stomp = pytest.mark.skip(reason="need --stomp option to run")
    for item in items:
        if "stomp" in item.keywords:
            item.add_marker(skip_stomp)

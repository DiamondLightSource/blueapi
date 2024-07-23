from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

from blueapi.service import interface
from blueapi.service.model import EnvironmentResponse
from blueapi.service.runner import InvalidRunnerStateError, WorkerDispatcher


def test_initialize():
    runner = WorkerDispatcher()
    assert not runner.state.initialized
    runner.start()
    assert runner.state.initialized
    # Run a single call to the runner for coverage of dispatch to subprocess
    assert runner.run(interface.get_worker_state)
    runner.stop()
    assert not runner.state.initialized


def test_reload():
    runner = WorkerDispatcher()
    runner.start()
    assert runner.state.initialized
    runner.reload()
    assert runner.state.initialized
    runner.stop()


def test_raises_if_used_before_started():
    runner = WorkerDispatcher()
    with pytest.raises(InvalidRunnerStateError):
        assert runner.run(interface.get_plans) is None


def test_error_on_runner_setup():
    runner = WorkerDispatcher(use_subprocess=False)
    expected_state = EnvironmentResponse(
        initialized=False,
        error_message="Intentional start_worker exception",
    )

    with mock.patch(
        "blueapi.service.runner.setup",
        side_effect=Exception("Intentional start_worker exception"),
    ):
        # Calling reload here instead of start also indirectly
        # tests that stop() doesn't raise if there is no error message
        # and the runner is not yet initialised
        runner.reload()
        state = runner.state
        assert state == expected_state


def start_worker_mock():
    yield SyntaxError("invalid syntax")
    yield None


@patch("blueapi.service.runner.Pool")
def test_can_reload_after_an_error(pool_mock: MagicMock):
    another_mock = MagicMock()
    pool_mock.return_value = another_mock

    # This test ensures the subprocess worker can be reloaded
    # after failing to initialise

    # all calls to subprocess (poll::apply) are mocked
    subprocess_calls_return_values = [
        SyntaxError("invalid code"),  # start_worker
        None,  # stop_worker
        None,  # start_worker
    ]

    another_mock.apply.side_effect = subprocess_calls_return_values

    runner = WorkerDispatcher(use_subprocess=True)
    runner.start()

    assert runner.state == EnvironmentResponse(
        initialized=False, error_message="invalid code"
    )

    runner.reload()

    assert runner.state == EnvironmentResponse(initialized=True, error_message=None)

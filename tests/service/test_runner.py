from unittest import mock

import pytest

from blueapi.service import interface
from blueapi.service.model import EnvironmentResponse
from blueapi.service.runner import RunnerNotStartedError, WorkerDispatcher


def test_initialize():
    runner = WorkerDispatcher()
    assert not runner.state.initialized
    runner.start()
    assert runner.state.initialized
    # Run a single call to the runner for coverage of dispatch to subprocess
    assert runner.run(interface.get_state)
    runner.stop()
    assert not runner.state.initialized


def test_reload():
    runner = WorkerDispatcher()
    runner.start()
    assert runner.state.initialized
    runner.reload_context()
    assert runner.state.initialized
    runner.stop()


def test_raises_if_used_before_started():
    runner = WorkerDispatcher()
    with pytest.raises(RunnerNotStartedError):
        assert runner.run(interface.get_plans) is None


def test_error_on_runner_setup():
    runner = WorkerDispatcher(use_subprocess=False)
    expected_state = EnvironmentResponse(
        initialized=False,
        error_message="Error configuring blueapi: Intentional start_worker exception",
    )

    with mock.patch(
        "blueapi.service.runner.start_worker",
        side_effect=Exception("Intentional start_worker exception"),
    ):
        # Calling reload here instead of start also indirectly
        # tests that stop() doesn't raise if there is no error message
        # and the runner is not yet initialised
        runner.reload_context()
        state = runner.state
        assert state == expected_state

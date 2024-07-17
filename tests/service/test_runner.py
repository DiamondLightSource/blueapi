from unittest import mock

import pytest

from blueapi.service import interface
from blueapi.service.model import EnvironmentResponse
from blueapi.service.runner import Runner, RunnerNotStartedError


def test_initialize():
    sp_handler = Runner()
    assert not sp_handler.state.initialized
    sp_handler.start()
    assert sp_handler.state.initialized
    # Run a single call to the handler for coverage of dispatch to subprocess
    assert sp_handler.run(interface.get_state)
    sp_handler.stop()
    assert not sp_handler.state.initialized


def test_reload():
    sp_handler = Runner()
    sp_handler.start()
    assert sp_handler.state.initialized
    sp_handler.reload_context()
    assert sp_handler.state.initialized
    sp_handler.stop()


def test_raises_if_used_before_started():
    sp_handler = Runner()
    with pytest.raises(RunnerNotStartedError):
        assert sp_handler.run(interface.get_plans) is None


def test_error_on_handler_setup():
    runner = Runner(use_subprocess=False)
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

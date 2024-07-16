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


def test_raises_if_not_started():
    sp_handler = Runner()
    with pytest.raises(RunnerNotStartedError):
        assert sp_handler.run(interface.get_plans) is None


def test_error_on_handler_setup():
    sp_handler = Runner()
    expected_state = EnvironmentResponse(
        initialized=False,
        error_message="Error configuring blueapi: Can't pickle "
        "<class 'unittest.mock.MagicMock'>: it's not the same object as "
        "unittest.mock.MagicMock",
    )

    # Using a mock for setup_handler causes a failure as the mock is not pickleable
    # An exception is set on the mock too but this is never reached
    with mock.patch(
        "blueapi.service.interface.start_worker",
        side_effect=Exception("Mock start_worker exception"),
    ):
        sp_handler.reload_context()
        state = sp_handler.state
        assert state == expected_state
    sp_handler.stop()

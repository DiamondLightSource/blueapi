from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

from blueapi.service.handler_base import BlueskyHandler, HandlerNotStartedError
from blueapi.service.model import (
    DeviceModel,
    EnvironmentResponse,
    PlanModel,
    WorkerTask,
)
from blueapi.service.subprocess_handler import SubprocessHandler
from blueapi.worker.event import TaskStatusEnum, WorkerState
from blueapi.worker.task import Task
from blueapi.worker.worker import TrackableTask

tasks_data = [
    TrackableTask(task_id="0", task=Task(name="sleep", params={"time": 0.0})),
    TrackableTask(
        task_id="1", task=Task(name="first_task"), is_complete=False, is_pending=True
    ),
    TrackableTask(
        task_id="2", task=Task(name="second_task"), is_complete=False, is_pending=False
    ),
    TrackableTask(
        task_id="3", task=Task(name="third_task"), is_complete=True, is_pending=False
    ),
    TrackableTask(
        task_id="4", task=Task(name="fourth_task"), is_complete=False, is_pending=True
    ),
]


def test_initialize():
    sp_handler = SubprocessHandler()
    assert not sp_handler.state.initialized
    sp_handler.start()
    assert sp_handler.state.initialized
    # Run a single call to the handler for coverage of dispatch to subprocess
    assert sp_handler.tasks == []
    sp_handler.stop()
    assert not sp_handler.state.initialized


def test_reload():
    sp_handler = SubprocessHandler()
    sp_handler.start()
    assert sp_handler.state.initialized
    sp_handler.reload_context()
    assert sp_handler.state.initialized
    sp_handler.stop()


def test_raises_if_not_started():
    sp_handler = SubprocessHandler()
    with pytest.raises(HandlerNotStartedError):
        assert sp_handler.worker_state is None


def test_error_on_handler_setup():
    sp_handler = SubprocessHandler()
    expected_state = EnvironmentResponse(
        initialized=False,
        error_message="Error configuring blueapi: Can't pickle "
        "<class 'unittest.mock.MagicMock'>: it's not the same object as "
        "unittest.mock.MagicMock",
    )

    # Using a mock for setup_handler causes a failure as the mock is not pickleable
    # An exception is set on the mock too but this is never reached
    with mock.patch(
        "blueapi.service.subprocess_handler.setup_handler",
        side_effect=Exception("Mock setup_handler exception"),
    ):
        sp_handler.reload_context()
        state = sp_handler.state
        assert state == expected_state
    sp_handler.stop()

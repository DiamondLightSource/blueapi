import os

import pytest

from blueapi.client.client import BlueapiClient
from blueapi.client.event_bus import AnyEvent
from blueapi.core.bluesky_types import DataEvent
from blueapi.worker.event import TaskStatus, WorkerEvent, WorkerState

_BEAMLINE = os.environ.get("BEAMLINE", "")

_DISABLE_SIDE_EFFECTS = bool(os.environ.get("DISABLE_SIDE_EFFECTS", 0))
_DISABLE_SIDE_EFFECTS_MESSAGE = """
    This test would cause side effects on the beamline, it has been disabled
    so as not to interfere with operation. To run tests that may interfere with
    the beamline export DISABLE_SIDE_EFFECTS=0 or add to add to env in pyproject.toml
    """
disable_side_effects = pytest.mark.skipif(
    _DISABLE_SIDE_EFFECTS, reason=_DISABLE_SIDE_EFFECTS_MESSAGE
)

_REQUIRES_AUTH_MESSAGE = """
Authentication credentials are required to run this test.
The test has been skipped because authentication is currently disabled.
For more details, see: https://github.com/DiamondLightSource/blueapi/issues/676.
"""
requires_auth = pytest.mark.xfail(reason=_REQUIRES_AUTH_MESSAGE)

# Mark for beamline-specific tests
_BEAMLINE_SPECIFIC_MESSAGE = """
    This test is beamline-specific but no beamline has been set.
    Set the BEAMLINE environment variable to enable this test in pyproject.toml
    """
beamline_specific_test = pytest.mark.skipif(
    not _BEAMLINE, reason=_BEAMLINE_SPECIFIC_MESSAGE
)


def clean_existing_tasks(client: BlueapiClient) -> None:
    for task in client.get_all_tasks().tasks:
        client.clear_task(task.task_id)


def check_all_events(all_events: list[AnyEvent]):
    assert isinstance(all_events[0], WorkerEvent) and all_events[0].task_status
    task_id = all_events[0].task_status.task_id
    # First event is WorkerEvent
    assert all_events[0] == WorkerEvent(
        state=WorkerState.RUNNING,
        task_status=TaskStatus(
            task_id=task_id,
            task_complete=False,
            task_failed=False,
        ),
    )

    assert all(
        isinstance(event, DataEvent) for event in all_events[1:-2]
    ), "Middle elements must be DataEvents."

    # Last 2 events are WorkerEvent
    assert all_events[-2:] == [
        WorkerEvent(
            state=WorkerState.IDLE,
            task_status=TaskStatus(
                task_id=task_id,
                task_complete=False,
                task_failed=False,
            ),
        ),
        WorkerEvent(
            state=WorkerState.IDLE,
            task_status=TaskStatus(
                task_id=task_id,
                task_complete=True,
                task_failed=False,
            ),
        ),
    ]

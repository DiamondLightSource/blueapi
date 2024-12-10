import os
from pathlib import Path

import pytest
from bluesky_stomp.models import BasicAuthentication

from blueapi.client.client import BlueapiClient
from blueapi.client.event_bus import AnyEvent
from blueapi.config import ApplicationConfig, RestConfig, StompConfig
from blueapi.worker.event import TaskStatus, WorkerEvent, WorkerState
from blueapi.worker.task import Task

BEAMLINE = os.environ.get("BEAMLINE", "p46")

DISABLE_SIDE_EFFECTS = bool(os.environ.get("DISABLE_SIDE_EFFECTS", 0))
DISABLE_SIDE_EFFECTS_MESSAGE = """
    This test would cause side effects on the beamline, it has been disabled
    so as not to interfere with operation. To run tests that may interfere with
    the beamline export DISABLE_SIDE_EFFECTS=0
    """
disable_side_effects = pytest.mark.skipif(
    DISABLE_SIDE_EFFECTS, reason=DISABLE_SIDE_EFFECTS_MESSAGE
)

VISIT_DIRECTORY: Path = {
    "p46": Path("/exports/mybeamline/p46/data/2024/cm11111-1/"),
    "p47": Path("/exports/mybeamline/p47/data/2024/cm11111-1/"),
}[BEAMLINE]

VISIT_NOT_MOUNTED = not (VISIT_DIRECTORY.exists() and VISIT_DIRECTORY.is_dir())

VISIT_NOT_MOUNTED_MESSAGE = f"""
    This test inspects data so it has to run on a machine that mounts
    {VISIT_DIRECTORY}
"""


@pytest.fixture
def training_rig_config() -> ApplicationConfig:
    return ApplicationConfig(
        stomp=StompConfig(
            host="daq-rabbitmq",
            auth=BasicAuthentication(username="guest", password="guest"),  # type: ignore
        ),
        api=RestConfig(host="p46-blueapi.diamond.ac.uk", port=443, protocol="https"),
    )


@pytest.fixture
def client(training_rig_config) -> BlueapiClient:
    return BlueapiClient.from_config(config=training_rig_config)


STEP_SCAN = Task(
    name="plan_step_scan",
    params={
        "detectors": ["det"],
        "motor": "sample_stage",
    },
)


@disable_side_effects
def test_step_scan_task(client: BlueapiClient, plan: str = "plan_step_scan"):
    assert client.get_plan(plan), f"In {plan} is available"

    all_events: list[AnyEvent] = []

    def on_event(event: AnyEvent):
        all_events.append(event)

    client.run_task(STEP_SCAN, on_event=on_event)
    assert isinstance(all_events[0], WorkerEvent) and all_events[0].task_status
    task_id = all_events[0].task_status.task_id
    assert all_events == [
        WorkerEvent(
            state=WorkerState.RUNNING,
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

    assert client.get_state() is WorkerState.IDLE

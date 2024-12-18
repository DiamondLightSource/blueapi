import pytest

from blueapi.client.client import BlueapiClient
from blueapi.client.event_bus import AnyEvent
from blueapi.worker.event import WorkerState
from blueapi.worker.task import Task
from tests.system_tests.common import (
    beamline_specific_test,
    check_all_events,
    disable_side_effects,
)


@disable_side_effects
@beamline_specific_test
@pytest.mark.parametrize("plan", ["plan_step_scan"])
def test_spec_scan_task(
    client_with_stomp: BlueapiClient,
    task_definition: dict[str, Task],
    plan,
):
    assert client_with_stomp.get_plan(plan), f"In {plan} is available"

    all_events: list[AnyEvent] = []

    def on_event(event: AnyEvent):
        all_events.append(event)

    client_with_stomp.run_task(task_definition[plan], on_event=on_event)

    check_all_events(all_events)

    assert client_with_stomp.get_state() is WorkerState.IDLE

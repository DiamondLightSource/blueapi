from collections.abc import Callable
from unittest.mock import MagicMock, Mock, call

import pytest
from bluesky_stomp.messaging import MessageContext
from observability_utils.tracing import (
    JsonObjectSpanExporter,
    asserting_span_exporter,
)

from blueapi.client.client import BlueapiClient
from blueapi.client.event_bus import AnyEvent, BlueskyStreamingError, EventBusClient
from blueapi.client.rest import BlueapiRestClient, BlueskyRemoteControlError
from blueapi.core import DataEvent
from blueapi.service.model import (
    DeviceModel,
    DeviceResponse,
    EnvironmentResponse,
    PlanModel,
    PlanResponse,
    TaskResponse,
    TasksListResponse,
    WorkerTask,
)
from blueapi.worker import ProgressEvent, Task, TrackableTask, WorkerEvent, WorkerState
from blueapi.worker.event import TaskStatus

PLANS = PlanResponse(
    plans=[
        PlanModel(name="foo"),
        PlanModel(name="bar"),
    ]
)
PLAN = PlanModel(name="foo")
DEVICES = DeviceResponse(
    devices=[
        DeviceModel(name="foo", protocols=[]),
        DeviceModel(name="bar", protocols=[]),
    ]
)
DEVICE = DeviceModel(name="foo", protocols=[])
TASK = TrackableTask(task_id="foo", task=Task(name="bar", params={}))
TASKS = TasksListResponse(tasks=[TASK])
ACTIVE_TASK = WorkerTask(task_id="bar")
ENV = EnvironmentResponse(initialized=True)
COMPLETE_EVENT = WorkerEvent(
    state=WorkerState.IDLE,
    task_status=TaskStatus(
        task_id="foo",
        task_complete=True,
        task_failed=False,
    ),
)
FAILED_EVENT = WorkerEvent(
    state=WorkerState.IDLE,
    task_status=TaskStatus(
        task_id="foo",
        task_complete=True,
        task_failed=True,
    ),
)


@pytest.fixture
def mock_rest() -> BlueapiRestClient:
    mock = Mock(spec=BlueapiRestClient)

    mock.get_plans.return_value = PLANS
    mock.get_plan.return_value = PLAN
    mock.get_devices.return_value = DEVICES
    mock.get_device.return_value = DEVICE
    mock.get_state.return_value = WorkerState.IDLE
    mock.get_task.return_value = TASK
    mock.get_all_tasks.return_value = TASKS
    mock.get_active_task.return_value = ACTIVE_TASK
    mock.get_environment.return_value = ENV
    mock.delete_environment.return_value = EnvironmentResponse(initialized=False)

    return mock


@pytest.fixture
def mock_events() -> EventBusClient:
    mock_events = MagicMock(spec=EventBusClient)
    ctx = Mock()
    ctx.correlation_id = "foo"
    mock_events.subscribe_to_all_events = lambda on_event: on_event(ctx, COMPLETE_EVENT)
    return mock_events


@pytest.fixture
def client(mock_rest: Mock) -> BlueapiClient:
    return BlueapiClient(rest=mock_rest)


@pytest.fixture
def client_with_events(mock_rest: Mock, mock_events: MagicMock):
    return BlueapiClient(rest=mock_rest, events=mock_events)


def test_get_plans(client: BlueapiClient):
    assert client.get_plans() == PLANS


def test_get_plan(client: BlueapiClient):
    assert client.get_plan("foo") == PLAN


def test_get_nonexistant_plan(
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.get_plan.side_effect = KeyError("Not found")
    with pytest.raises(KeyError):
        client.get_plan("baz")


def test_get_devices(client: BlueapiClient):
    assert client.get_devices() == DEVICES


def test_get_device(client: BlueapiClient):
    assert client.get_device("foo") == DEVICE


def test_get_nonexistant_device(
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.get_device.side_effect = KeyError("Not found")
    with pytest.raises(KeyError):
        client.get_device("baz")


def test_get_state(client: BlueapiClient):
    assert client.get_state() == WorkerState.IDLE


def test_get_task(client: BlueapiClient):
    assert client.get_task("foo") == TASK


def test_get_nonexistent_task(
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.get_task.side_effect = KeyError("Not found")
    with pytest.raises(KeyError):
        client.get_task("baz")


def test_get_task_with_empty_id(client: BlueapiClient):
    with pytest.raises(AssertionError) as exc:
        client.get_task("")
        assert str(exc) == "Task ID not provided!"


def test_get_all_tasks(
    client: BlueapiClient,
):
    assert client.get_all_tasks() == TASKS


def test_create_task(
    client: BlueapiClient,
    mock_rest: Mock,
):
    client.create_task(task=Task(name="foo"))
    mock_rest.create_task.assert_called_once_with(Task(name="foo"))


def test_create_task_does_not_start_task(
    client: BlueapiClient,
    mock_rest: Mock,
):
    client.create_task(task=Task(name="foo"))
    mock_rest.update_worker_task.assert_not_called()


def test_clear_task(
    client: BlueapiClient,
    mock_rest: Mock,
):
    client.clear_task(task_id="foo")
    mock_rest.clear_task.assert_called_once_with("foo")


def test_get_active_task(client: BlueapiClient):
    assert client.get_active_task() == ACTIVE_TASK


def test_start_task(
    client: BlueapiClient,
    mock_rest: Mock,
):
    client.start_task(task=WorkerTask(task_id="bar"))
    mock_rest.update_worker_task.assert_called_once_with(WorkerTask(task_id="bar"))


def test_start_nonexistant_task(
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.update_worker_task.side_effect = KeyError("Not found")
    with pytest.raises(KeyError):
        client.start_task(task=WorkerTask(task_id="bar"))


def test_create_and_start_task_calls_both_creating_and_starting_endpoints(
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.create_task.return_value = TaskResponse(task_id="baz")
    mock_rest.update_worker_task.return_value = TaskResponse(task_id="baz")
    client.create_and_start_task(Task(name="baz"))
    mock_rest.create_task.assert_called_once_with(Task(name="baz"))
    mock_rest.update_worker_task.assert_called_once_with(WorkerTask(task_id="baz"))


def test_create_and_start_task_fails_if_task_creation_fails(
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.create_task.side_effect = BlueskyRemoteControlError("No can do")
    with pytest.raises(BlueskyRemoteControlError):
        client.create_and_start_task(Task(name="baz"))


def test_create_and_start_task_fails_if_task_id_is_wrong(
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.create_task.return_value = TaskResponse(task_id="baz")
    mock_rest.update_worker_task.return_value = TaskResponse(task_id="bar")
    with pytest.raises(BlueskyRemoteControlError):
        client.create_and_start_task(Task(name="baz"))


def test_create_and_start_task_fails_if_task_start_fails(
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.create_task.return_value = TaskResponse(task_id="baz")
    mock_rest.update_worker_task.side_effect = BlueskyRemoteControlError("No can do")
    with pytest.raises(BlueskyRemoteControlError):
        client.create_and_start_task(Task(name="baz"))


def test_get_environment(client: BlueapiClient):
    assert client.get_environment() == ENV


def test_reload_environment(
    client: BlueapiClient,
    mock_rest: Mock,
):
    client.reload_environment()
    mock_rest.get_environment.assert_called_once()
    mock_rest.delete_environment.assert_called_once()


def test_reload_environment_failure(
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.get_environment.return_value = EnvironmentResponse(
        initialized=False, error_message="foo"
    )
    with pytest.raises(BlueskyRemoteControlError, match="foo"):
        client.reload_environment()


def test_abort(
    client: BlueapiClient,
    mock_rest: Mock,
):
    client.abort(reason="foo")
    mock_rest.cancel_current_task.assert_called_once_with(
        WorkerState.ABORTING,
        reason="foo",
    )


def test_stop(
    client: BlueapiClient,
    mock_rest: Mock,
):
    client.stop()
    mock_rest.cancel_current_task.assert_called_once_with(WorkerState.STOPPING)


def test_pause(
    client: BlueapiClient,
    mock_rest: Mock,
):
    client.pause(defer=True)
    mock_rest.set_state.assert_called_once_with(
        WorkerState.PAUSED,
        defer=True,
    )


def test_resume(
    client: BlueapiClient,
    mock_rest: Mock,
):
    client.resume()
    mock_rest.set_state.assert_called_once_with(
        WorkerState.RUNNING,
        defer=False,
    )


def test_cannot_run_task_without_message_bus(client: BlueapiClient):
    with pytest.raises(
        RuntimeError,
        match="Cannot run plans without Stomp configuration to track progress",
    ):
        client.run_task(Task(name="foo"))


def test_run_task_sets_up_control(
    client_with_events: BlueapiClient,
    mock_rest: Mock,
    mock_events: MagicMock,
):
    mock_rest.create_task.return_value = TaskResponse(task_id="foo")
    mock_rest.update_worker_task.return_value = TaskResponse(task_id="foo")
    ctx = Mock()
    ctx.correlation_id = "foo"
    mock_events.subscribe_to_all_events = lambda on_event: on_event(COMPLETE_EVENT, ctx)

    client_with_events.run_task(Task(name="foo"))
    mock_rest.create_task.assert_called_once_with(Task(name="foo"))
    mock_rest.update_worker_task.assert_called_once_with(WorkerTask(task_id="foo"))


def test_run_task_fails_on_failing_event(
    client_with_events: BlueapiClient,
    mock_rest: Mock,
    mock_events: MagicMock,
):
    mock_rest.create_task.return_value = TaskResponse(task_id="foo")
    mock_rest.update_worker_task.return_value = TaskResponse(task_id="foo")

    ctx = Mock()
    ctx.correlation_id = "foo"
    mock_events.subscribe_to_all_events = lambda on_event: on_event(FAILED_EVENT, ctx)

    on_event = Mock()
    with pytest.raises(BlueskyStreamingError):
        client_with_events.run_task(Task(name="foo"), on_event=on_event)

    on_event.assert_called_with(FAILED_EVENT)


@pytest.mark.parametrize(
    "test_event",
    [
        WorkerEvent(
            state=WorkerState.RUNNING,
            task_status=TaskStatus(
                task_id="foo",
                task_complete=False,
                task_failed=False,
            ),
        ),
        ProgressEvent(task_id="foo"),
        DataEvent(name="start", doc={}),
    ],
)
def test_run_task_calls_event_callback(
    client_with_events: BlueapiClient,
    mock_rest: Mock,
    mock_events: MagicMock,
    test_event: AnyEvent,
):
    mock_rest.create_task.return_value = TaskResponse(task_id="foo")
    mock_rest.update_worker_task.return_value = TaskResponse(task_id="foo")

    ctx = Mock()
    ctx.correlation_id = "foo"

    def callback(on_event: Callable[[AnyEvent, MessageContext], None]):
        on_event(test_event, ctx)
        on_event(COMPLETE_EVENT, ctx)

    mock_events.subscribe_to_all_events = callback  # type: ignore

    mock_on_event = Mock()
    client_with_events.run_task(Task(name="foo"), on_event=mock_on_event)

    assert mock_on_event.mock_calls == [call(test_event), call(COMPLETE_EVENT)]


@pytest.mark.parametrize(
    "test_event",
    [
        WorkerEvent(
            state=WorkerState.RUNNING,
            task_status=TaskStatus(
                task_id="bar",
                task_complete=False,
                task_failed=False,
            ),
        ),
        ProgressEvent(task_id="bar"),
        object(),
    ],
)
def test_run_task_ignores_non_matching_events(
    client_with_events: BlueapiClient,
    mock_rest: Mock,
    mock_events: MagicMock,
    test_event: AnyEvent,
):
    mock_rest.create_task.return_value = TaskResponse(task_id="foo")  # type: ignore
    mock_rest.update_worker_task.return_value = TaskResponse(task_id="foo")  # type: ignore

    ctx = Mock()
    ctx.correlation_id = "foo"

    def callback(on_event: Callable[[AnyEvent, MessageContext], None]):
        on_event(test_event, ctx)  # type: ignore
        on_event(COMPLETE_EVENT, ctx)

    mock_events.subscribe_to_all_events = callback

    mock_on_event = Mock()
    client_with_events.run_task(Task(name="foo"), on_event=mock_on_event)

    mock_on_event.assert_called_once_with(COMPLETE_EVENT)


def test_get_plans_span_ok(exporter: JsonObjectSpanExporter, client: BlueapiClient):
    with asserting_span_exporter(exporter, "get_plans"):
        client.get_plans()


def test_get_plan_span_ok(exporter: JsonObjectSpanExporter, client: BlueapiClient):
    with asserting_span_exporter(exporter, "get_plan", "name"):
        client.get_plan("foo")


def test_get_devices_span_ok(exporter: JsonObjectSpanExporter, client: BlueapiClient):
    with asserting_span_exporter(exporter, "get_devices"):
        client.get_devices()


def test_get_device_span_ok(exporter: JsonObjectSpanExporter, client: BlueapiClient):
    with asserting_span_exporter(exporter, "get_device", "name"):
        client.get_device("foo")


def test_get_state_ok(exporter: JsonObjectSpanExporter, client: BlueapiClient):
    with asserting_span_exporter(exporter, "get_state"):
        client.get_state()


def test_get_task_span_ok(exporter: JsonObjectSpanExporter, client: BlueapiClient):
    with asserting_span_exporter(exporter, "get_task", "task_id"):
        client.get_task("foo")


def test_get_all_tasks_span_ok(
    exporter: JsonObjectSpanExporter,
    client: BlueapiClient,
):
    with asserting_span_exporter(exporter, "get_all_tasks"):
        client.get_all_tasks()


def test_create_task_span_ok(
    exporter: JsonObjectSpanExporter,
    client: BlueapiClient,
    mock_rest: Mock,
):
    with asserting_span_exporter(exporter, "create_task", "task"):
        client.create_task(task=Task(name="foo"))


def test_clear_task_span_ok(
    exporter: JsonObjectSpanExporter,
    client: BlueapiClient,
    mock_rest: Mock,
):
    with asserting_span_exporter(exporter, "clear_task"):
        client.clear_task(task_id="foo")


def test_get_active_task_span_ok(
    exporter: JsonObjectSpanExporter, client: BlueapiClient
):
    with asserting_span_exporter(exporter, "get_active_task"):
        client.get_active_task()


def test_start_task_span_ok(
    exporter: JsonObjectSpanExporter,
    client: BlueapiClient,
    mock_rest: Mock,
):
    with asserting_span_exporter(exporter, "start_task", "task"):
        client.start_task(task=WorkerTask(task_id="bar"))


def test_create_and_start_task_span_ok(
    exporter: JsonObjectSpanExporter,
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.create_task.return_value = TaskResponse(task_id="baz")
    mock_rest.update_worker_task.return_value = TaskResponse(task_id="baz")
    with asserting_span_exporter(exporter, "create_and_start_task", "task"):
        client.create_and_start_task(Task(name="baz"))


def test_get_environment_span_ok(
    exporter: JsonObjectSpanExporter, client: BlueapiClient
):
    with asserting_span_exporter(exporter, "get_environment"):
        client.get_environment()


def test_reload_environment_span_ok(
    exporter: JsonObjectSpanExporter,
    client: BlueapiClient,
    mock_rest: Mock,
):
    with asserting_span_exporter(exporter, "reload_environment"):
        client.reload_environment()


def test_abort_span_ok(
    exporter: JsonObjectSpanExporter,
    client: BlueapiClient,
    mock_rest: Mock,
):
    with asserting_span_exporter(exporter, "abort", "reason"):
        client.abort(reason="foo")


def test_stop_span_ok(
    exporter: JsonObjectSpanExporter,
    client: BlueapiClient,
    mock_rest: Mock,
):
    with asserting_span_exporter(exporter, "stop"):
        client.stop()


def test_pause_span_ok(
    exporter: JsonObjectSpanExporter,
    client: BlueapiClient,
    mock_rest: Mock,
):
    with asserting_span_exporter(exporter, "pause"):
        client.pause(defer=True)


def test_resume_span_ok(
    exporter: JsonObjectSpanExporter,
    client: BlueapiClient,
    mock_rest: Mock,
):
    with asserting_span_exporter(exporter, "resume"):
        client.resume()


def test_cannot_run_task_span_ok(
    exporter: JsonObjectSpanExporter, client: BlueapiClient
):
    with pytest.raises(
        RuntimeError,
        match="Cannot run plans without Stomp configuration to track progress",
    ):
        with asserting_span_exporter(exporter, "grun_task"):
            client.run_task(Task(name="foo"))

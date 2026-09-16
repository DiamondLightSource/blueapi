from collections.abc import Callable
from unittest.mock import MagicMock, Mock, call, patch

import pytest
from bluesky_stomp.messaging import MessageContext
from observability_utils.tracing import JsonObjectSpanExporter, asserting_span_exporter
from pydantic import HttpUrl
from tests.unit_tests.client.constants import (
    ACTIVE_TASK,
    COMPLETE_EVENT,
    DEVICE,
    DEVICES,
    ENV,
    ENVIRONMENT_ID,
    FAILED_EVENT,
    NEW_ENV,
    PLAN,
    PLANS,
)

from blueapi.client import BlueapiClient
from blueapi.client.client import MissingInstrumentSessionError
from blueapi.client.event_bus import AnyEvent, EventBusClient
from blueapi.client.plan_cache import Plan, PlanFailedError
from blueapi.client.rest import (
    BlueskyRemoteControlError,
    BlueskyRequestError,
    ServiceUnavailableError,
)
from blueapi.config import MissingStompConfigurationError
from blueapi.core import DataEvent
from blueapi.service.model import (
    DeviceModel,
    DeviceResponse,
    EnvironmentResponse,
    PlanModel,
    PlanResponse,
    ProtocolInfo,
    TaskRequest,
    TaskResponse,
    WorkerTask,
)
from blueapi.worker import ProgressEvent, WorkerEvent, WorkerState
from blueapi.worker.event import TaskError, TaskResult, TaskStatus


@pytest.fixture
def mock_events() -> EventBusClient:
    mock_events = MagicMock(spec=EventBusClient)
    ctx = Mock()
    ctx.correlation_id = "foo"
    mock_events.subscribe_to_all_events = lambda on_event: on_event(ctx, COMPLETE_EVENT)
    return mock_events


@pytest.fixture
def client_with_events(mock_rest: Mock, mock_events: MagicMock):
    return BlueapiClient(rest=mock_rest, events=mock_events)


def test_client_from_config():
    bc = BlueapiClient.from_config_file(
        "tests/unit_tests/valid_example_config/client.yaml"
    )
    assert bc._rest._config.url == HttpUrl("http://example.com:8082")


def test_get_plans(client: BlueapiClient):
    assert PlanResponse(plans=[p.model for p in client.plans]) == PLANS


def test_get_plan(client: BlueapiClient):
    assert client.plans.foo.model == PLAN
    assert client.plans["foo"].model == PLAN


def test_print_plans(client: BlueapiClient, capsys: pytest.CaptureFixture):
    client.print_plans()
    captured = capsys.readouterr()
    for dev in PLANS.plans:
        assert dev.name in captured.out


def test_get_nonexistant_plan(
    client: BlueapiClient,
):
    with pytest.raises(AttributeError):
        _ = client.plans.fizz_buzz.model


def test_get_devices(client: BlueapiClient):
    assert DeviceResponse(devices=[d.model for d in client.devices]) == DEVICES


def test_get_device(client: BlueapiClient):
    assert client.devices.foo.model == DEVICE


def test_print_devices(client: BlueapiClient, capsys: pytest.CaptureFixture):
    client.print_devices()
    captured = capsys.readouterr()
    for dev in DEVICES.devices:
        assert dev.name in captured.out


def test_get_nonexistent_device(
    client: BlueapiClient,
):
    with pytest.raises(AttributeError):
        _ = client.devices.baz


def test_get_child_device(mock_rest: Mock, client: BlueapiClient):
    mock_rest.get_device.side_effect = lambda name: (
        DeviceModel(name="foo.x", protocols=[ProtocolInfo(name="One")])
        if name == "foo.x"
        else None
    )
    foo = client.devices.foo
    assert foo.model.name == "foo"
    x = client.devices.foo.x
    assert x.model.name == "foo.x"


def test_state_property(client: BlueapiClient):
    assert client.state == WorkerState.IDLE


def test_get_state(client: BlueapiClient):
    assert client.get_state() == WorkerState.IDLE


def test_active_task_property(client: BlueapiClient):
    assert client.active_task == ACTIVE_TASK


def test_get_active_task(client: BlueapiClient):
    assert client.get_active_task() == ACTIVE_TASK


def test_create_and_start_task_calls_both_creating_and_starting_endpoints(
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.create_task.return_value = TaskResponse(task_id="baz")
    mock_rest.update_worker_task.return_value = TaskResponse(task_id="baz")
    client.create_and_start_task(
        TaskRequest(name="baz", instrument_session="cm12345-1")
    )
    mock_rest.create_task.assert_called_once_with(
        TaskRequest(name="baz", instrument_session="cm12345-1")
    )
    mock_rest.update_worker_task.assert_called_once_with(WorkerTask(task_id="baz"))


def test_create_and_start_task_fails_if_task_creation_fails(
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.create_task.side_effect = BlueskyRemoteControlError("No can do")
    with pytest.raises(BlueskyRemoteControlError):
        client.create_and_start_task(
            TaskRequest(name="baz", instrument_session="cm12345-1")
        )


def test_create_and_start_task_fails_if_task_id_is_wrong(
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.create_task.return_value = TaskResponse(task_id="baz")
    mock_rest.update_worker_task.return_value = TaskResponse(task_id="bar")
    with pytest.raises(BlueskyRemoteControlError):
        client.create_and_start_task(
            TaskRequest(name="baz", instrument_session="cm12345-1")
        )


def test_create_and_start_task_fails_if_task_start_fails(
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.create_task.return_value = TaskResponse(task_id="baz")
    mock_rest.update_worker_task.side_effect = BlueskyRemoteControlError("No can do")
    with pytest.raises(BlueskyRemoteControlError):
        client.create_and_start_task(
            TaskRequest(name="baz", instrument_session="cm12345-1")
        )


def test_environment_property(client: BlueapiClient):
    assert client.environment == ENV


def test_get_environment(client: BlueapiClient):
    assert client.get_environment() == ENV


def test_reload_environment(
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.get_environment.return_value = NEW_ENV
    environment = client.reload_environment()
    mock_rest.get_environment.assert_called_once()
    mock_rest.delete_environment.assert_called_once()
    assert environment == NEW_ENV


def test_reload_environment_removes_caches(client: BlueapiClient, mock_rest: Mock):
    mock_rest.get_environment.return_value = NEW_ENV

    _ = client.plans, client.devices
    _ = client.plans, client.devices

    # rest calls only made once as plans/devices are cached
    mock_rest.get_plans.assert_called_once()
    mock_rest.get_devices.assert_called_once()
    mock_rest.reset_mock()

    client.reload_environment()
    _ = client.plans, client.devices

    # When environment is reloaded, caches are cleared so another call is required
    mock_rest.get_plans.assert_called_once()
    mock_rest.get_devices.assert_called_once()


@patch("blueapi.client.client.time.time")
@patch("blueapi.client.client.time.sleep")
def test_reload_environment_no_timeout(
    mock_sleep: Mock,
    mock_time: Mock,
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.get_environment.side_effect = [ENV, ENV, ENV, NEW_ENV]
    mock_time.return_value = 100.0
    environment = client.reload_environment(timeout=None)
    assert mock_sleep.call_count == 3
    assert environment == NEW_ENV


@patch("blueapi.client.client.time.time")
@patch("blueapi.client.client.time.sleep")
def test_reload_environment_with_timeout(
    _: Mock,
    mock_time: Mock,
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.get_environment.side_effect = [
        EnvironmentResponse(environment_id=ENVIRONMENT_ID, initialized=False)
    ] * 4
    mock_time.side_effect = [
        100.0,
        100.5,
        101.0,  # Timeout should occur here
        101.5,
    ]
    with pytest.raises(
        TimeoutError,
        match="Failed to reload the environment within 1.0 "
        "seconds, a server restart is recommended",
    ):
        client.reload_environment(timeout=1.0)


@patch("blueapi.client.client.time.time")
@patch("blueapi.client.client.time.sleep")
def test_reload_environment_ignores_current_environment(
    mock_sleep: Mock,
    mock_time: Mock,
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.get_environment.side_effect = [
        ENV,  # This is the old environment
        ENV,
        ENV,
        NEW_ENV,  # This is the new environment
    ]
    mock_time.return_value = 100.0
    environment = client.reload_environment(timeout=None)
    assert mock_sleep.call_count == 3
    assert environment == NEW_ENV


def test_reload_environment_failure(
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.get_environment.return_value = EnvironmentResponse(
        environment_id=ENVIRONMENT_ID, initialized=False, error_message="foo"
    )
    with pytest.raises(BlueskyRemoteControlError, match="foo"):
        client.reload_environment()


@pytest.mark.parametrize("err", [ServiceUnavailableError(), BlueskyRequestError()])
def test_reload_propagates_known_errors(
    err: Exception, client: BlueapiClient, mock_rest: Mock
):
    mock_rest.delete_environment.side_effect = err

    with pytest.raises(type(err)):
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
        MissingStompConfigurationError,
        match="Stomp configuration required to run plans is missing or disabled",
    ):
        client.run_task(TaskRequest(name="foo", instrument_session="cm12345-1"))


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

    client_with_events.run_task(TaskRequest(name="foo", instrument_session="cm12345-1"))
    mock_rest.create_task.assert_called_once_with(
        TaskRequest(name="foo", instrument_session="cm12345-1")
    )
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
    outcome = client_with_events.run_task(
        TaskRequest(name="foo", instrument_session="cm12345-1"),
        on_event=on_event,
    )
    assert outcome.task_failed
    assert outcome.task_complete
    assert isinstance(outcome.result, TaskError)
    assert outcome.result.message == "The plan failed"
    assert outcome.result.type == "PlanFailure"

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
                result=TaskError(type="ValueError", message="Task failed"),
            ),
        ),
        ProgressEvent(task_id="foo"),
        DataEvent(name="start", doc={}, task_id="0000-1111"),
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
    client_with_events.run_task(
        TaskRequest(name="foo", instrument_session="cm12345-1"), on_event=mock_on_event
    )

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
                result=None,
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
    client_with_events.run_task(
        TaskRequest(name="foo", instrument_session="cm12345-1"), on_event=mock_on_event
    )

    mock_on_event.assert_called_once_with(COMPLETE_EVENT)


def test_scripting_interface_returns_result():
    client = Mock(spec=BlueapiClient, instrument_session="cm12345-1")
    client.run_task.return_value = TaskStatus(
        task_id="foobar",
        task_complete=True,
        task_failed=False,
        result=TaskResult(result=42, type="int"),
    )
    demo_plan = Plan(
        client=client,
        model=PlanModel(name="demo", description="Demo plan", schema={}),
    )
    assert demo_plan() == 42


def test_scripting_interface_raises_exceptions():
    client = Mock(spec=BlueapiClient, instrument_session="cm12345-1")
    client.run_task.return_value = TaskStatus(
        task_id="foobar",
        task_complete=True,
        task_failed=True,
        result=TaskError(type="ValueError", message="Plan failed"),
    )
    demo_plan = Plan(
        client=client,
        model=PlanModel(name="demo", description="Demo plan", schema={}),
    )
    with pytest.raises(PlanFailedError, match="Plan failed"):
        demo_plan()


def test_oidc_config_property(client, mock_rest):
    assert client.oidc_config == mock_rest.get_oidc_config()


def test_get_oidc_config(client, mock_rest):
    assert client.get_oidc_config() == mock_rest.get_oidc_config()


def test_get_plans_span_ok(exporter: JsonObjectSpanExporter, client: BlueapiClient):
    with asserting_span_exporter(exporter, "plans"):
        _ = client.plans


def test_get_plan_span_ok(exporter: JsonObjectSpanExporter, client: BlueapiClient):
    with asserting_span_exporter(exporter, "plans"):
        _ = client.plans.foo


def test_get_devices_span_ok(exporter: JsonObjectSpanExporter, client: BlueapiClient):
    with asserting_span_exporter(exporter, "devices"):
        _ = client.devices


def test_get_device_span_ok(exporter: JsonObjectSpanExporter, client: BlueapiClient):
    with asserting_span_exporter(exporter, "devices"):
        _ = client.devices.foo


def test_get_state_span_ok(exporter: JsonObjectSpanExporter, client: BlueapiClient):
    with asserting_span_exporter(exporter, "state"):
        _ = client.state


def test_get_active_task_span_ok(
    exporter: JsonObjectSpanExporter, client: BlueapiClient
):
    with asserting_span_exporter(exporter, "active_task"):
        _ = client.active_task


def test_create_and_start_task_span_ok(
    exporter: JsonObjectSpanExporter,
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.create_task.return_value = TaskResponse(task_id="baz")
    mock_rest.update_worker_task.return_value = TaskResponse(task_id="baz")
    with asserting_span_exporter(exporter, "create_and_start_task", "task"):
        client.create_and_start_task(
            TaskRequest(name="baz", instrument_session="cm12345-1")
        )


def test_get_environment_span_ok(
    exporter: JsonObjectSpanExporter, client: BlueapiClient
):
    with asserting_span_exporter(exporter, "environment"):
        _ = client.environment


def test_reload_environment_span_ok(
    exporter: JsonObjectSpanExporter,
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.get_environment.return_value = NEW_ENV
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
        MissingStompConfigurationError,
        match="Stomp configuration required to run plans is missing or disabled",
    ):
        with asserting_span_exporter(exporter, "grun_task"):
            client.run_task(TaskRequest(name="foo", instrument_session="cm12345-1"))


def test_instrument_session_required(client):
    with pytest.raises(MissingInstrumentSessionError):
        _ = client.instrument_session


def test_setting_instrument_session(client):
    # This looks like a completely pointless test but instrument_session is a
    # property with some logic so it's not purely to get coverage up
    client.instrument_session = "cm12345-4"
    assert client.instrument_session == "cm12345-4"


def test_fluent_instrument_session_setter(client):
    client2 = client.with_instrument_session("cm12345-3")
    assert client is client2
    assert client.instrument_session == "cm12345-3"


def test_adding_removing_callback(client):
    def callback(*a, **kw):
        pass

    cb_id = client.add_callback(callback)
    assert len(client.callbacks) == 1
    client.remove_callback(cb_id)
    assert len(client.callbacks) == 0


@pytest.mark.parametrize(
    "test_event",
    [
        WorkerEvent(
            state=WorkerState.RUNNING,
            task_status=TaskStatus(
                task_id="foo",
                task_complete=False,
                task_failed=False,
                result=None,
            ),
        ),
        ProgressEvent(task_id="foo"),
        DataEvent(name="start", doc={}, task_id="0000-1111"),
    ],
)
def test_client_callbacks(
    client_with_events: BlueapiClient,
    mock_rest: Mock,
    mock_events: MagicMock,
    test_event: AnyEvent,
):
    callback = Mock()
    client_with_events.add_callback(callback)
    mock_rest.create_task.return_value = TaskResponse(task_id="foo")
    mock_rest.update_worker_task.return_value = TaskResponse(task_id="foo")

    ctx = Mock()
    ctx.correlation_id = "foo"

    def subscribe(on_event: Callable[[AnyEvent, MessageContext], None]):
        on_event(test_event, ctx)
        on_event(COMPLETE_EVENT, ctx)

    mock_events.subscribe_to_all_events = subscribe  # type: ignore

    client_with_events.run_task(TaskRequest(name="foo", instrument_session="cm12345-1"))

    assert callback.mock_calls == [call(test_event), call(COMPLETE_EVENT)]


def test_client_callback_failures(
    client_with_events: BlueapiClient,
    mock_rest: Mock,
    mock_events: MagicMock,
):
    failing_callback = Mock(side_effect=ValueError("Broken callback"))
    callback = Mock()
    client_with_events.add_callback(failing_callback)
    client_with_events.add_callback(callback)
    mock_rest.create_task.return_value = TaskResponse(task_id="foo")
    mock_rest.update_worker_task.return_value = TaskResponse(task_id="foo")

    ctx = Mock()
    ctx.correlation_id = "foo"

    evt = DataEvent(name="start", doc={}, task_id="foo")

    def subscribe(on_event: Callable[[AnyEvent, MessageContext], None]):
        on_event(evt, ctx)
        on_event(COMPLETE_EVENT, ctx)

    mock_events.subscribe_to_all_events = subscribe  # type: ignore

    client_with_events.run_task(TaskRequest(name="foo", instrument_session="cm12345-1"))

    assert failing_callback.mock_calls == [call(evt), call(COMPLETE_EVENT)]
    assert callback.mock_calls == [call(evt), call(COMPLETE_EVENT)]


@patch("blueapi.client.client.SessionManager")
def test_client_login_existing_login(mock_session_manager: Mock, client: BlueapiClient):
    client.login()

    mock_session_manager.from_cache.assert_called_once()
    mock_session_manager.from_cache().get_valid_access_token.assert_called_once()


@patch("blueapi.client.client.SessionManager")
def test_client_new_login(mock_session_manager: Mock, client: BlueapiClient):
    manager = Mock()
    manager.get_valid_access_token.side_effect = ValueError("No existing token")

    mock_session_manager.from_cache.return_value = manager

    client.login()

    mock_session_manager.assert_called_once()
    mock_session_manager.return_value.start_device_flow.assert_called_once()


@patch("blueapi.client.client.SessionManager")
def test_client_login_no_oidc(
    mock_session_manager: Mock, mock_rest: Mock, client: BlueapiClient
):
    mock_rest.get_oidc_config.return_value = None
    mock_session_manager.from_cache.return_value.get_valid_access_token.side_effect = (
        ValueError("No existing token")
    )

    client.login()

    mock_session_manager.assert_not_called()


def test_client_logout(mock_rest: Mock, client: BlueapiClient):
    mock_session_manager = Mock()
    mock_rest.session_manager = mock_session_manager

    client.logout()

    mock_session_manager.logout.assert_called_once()
    assert mock_rest.session_manager is None


@pytest.mark.parametrize("event", [COMPLETE_EVENT, FAILED_EVENT])
def test_run_blocking(event: WorkerEvent, client: BlueapiClient, mock_rest: Mock):
    mock_rest.run_blocking.side_effect = lambda req: [event]
    res = client.run_blocking(TaskRequest(name="foo", instrument_session="cm12345-1"))
    assert res == event.task_status


@pytest.mark.parametrize("event", [COMPLETE_EVENT, FAILED_EVENT])
def test_run_blocking_callbacks(
    event: WorkerEvent, client: BlueapiClient, mock_rest: Mock
):
    callback = Mock()
    mock_rest.run_blocking.side_effect = lambda req: [event]
    client.run_blocking(Mock(), on_event=callback)

    callback.assert_called_once_with(event)


@pytest.mark.parametrize("event", [COMPLETE_EVENT, FAILED_EVENT])
def test_run_blocking_client_callbacks(
    event: WorkerEvent, client: BlueapiClient, mock_rest: Mock
):
    callback = Mock()
    mock_rest.run_blocking.side_effect = lambda req: [event]
    client.add_callback(callback)
    client.run_blocking(Mock())

    callback.assert_called_once_with(event)


def test_run_blocking_error_if_cut_short(client: BlueapiClient, mock_rest: Mock):
    mock_rest.run_blocking.side_effect = lambda req: []
    with pytest.raises(
        BlueskyRemoteControlError, match="Connection closed before plan completed"
    ):
        client.run_blocking(Mock())


def test_run_blocking_ignores_callback_error(client: BlueapiClient, mock_rest: Mock):
    mock_rest.run_blocking.side_effect = lambda req: [COMPLETE_EVENT]

    def broken_callback(_: AnyEvent):
        raise Exception("This callback is broken")

    client.add_callback(broken_callback)
    res = client.run_blocking(Mock())
    assert res == COMPLETE_EVENT.task_status

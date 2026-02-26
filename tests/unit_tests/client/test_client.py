import uuid
from collections.abc import Callable
from unittest.mock import MagicMock, Mock, call, patch

import pytest
from bluesky_stomp.messaging import MessageContext
from observability_utils.tracing import (
    JsonObjectSpanExporter,
    asserting_span_exporter,
)
from pydantic import HttpUrl

from blueapi.client import BlueapiClient
from blueapi.client.client import (
    DeviceCache,
    DeviceRef,
    MissingInstrumentSessionError,
    Plan,
    PlanCache,
)
from blueapi.client.event_bus import AnyEvent, EventBusClient
from blueapi.client.rest import BlueapiRestClient, BlueskyRemoteControlError
from blueapi.config import MissingStompConfigurationError, StompConfig, TcpUrl
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
    TasksListResponse,
    WorkerTask,
)
from blueapi.worker import ProgressEvent, Task, TrackableTask, WorkerEvent, WorkerState
from blueapi.worker.event import TaskError, TaskResult, TaskStatus

PLANS = PlanResponse(
    plans=[
        PlanModel(name="foo"),
        PlanModel(name="bar"),
    ]
)
PLAN = PlanModel(name="foo")
FULL_PLAN = PlanModel(
    name="foobar",
    description="Description of plan foobar",
    schema={
        "title": "foobar",
        "description": "Model description of plan foobar",
        "properties": {
            "one": {},
            "two": {},
        },
        "required": ["one"],
    },
)
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
ENVIRONMENT_ID = uuid.uuid4()
NEW_ENVIRONMENT_ID = uuid.uuid4()
ENV = EnvironmentResponse(environment_id=ENVIRONMENT_ID, initialized=True)
NEW_ENV = EnvironmentResponse(environment_id=NEW_ENVIRONMENT_ID, initialized=True)
COMPLETE_EVENT = WorkerEvent(
    state=WorkerState.IDLE,
    task_status=TaskStatus(
        task_id="foo",
        task_complete=True,
        task_failed=False,
        result=TaskResult(type="NoneType", result=None),
    ),
)
FAILED_EVENT = WorkerEvent(
    state=WorkerState.IDLE,
    task_status=TaskStatus(
        task_id="foo",
        task_complete=True,
        task_failed=True,
        result=TaskError(type="PlanFailure", message="The plan failed"),
    ),
)


@pytest.fixture
def mock_rest() -> BlueapiRestClient:
    mock = Mock(spec=BlueapiRestClient)

    mock.get_plans.return_value = PLANS
    mock.get_plan.side_effect = lambda n: {p.name: p for p in PLANS.plans}[n]
    mock.get_devices.return_value = DEVICES
    mock.get_device.side_effect = lambda n: {d.name: d for d in DEVICES.devices}[n]
    mock.get_state.return_value = WorkerState.IDLE
    mock.get_task.return_value = TASK
    mock.get_all_tasks.return_value = TASKS
    mock.get_active_task.return_value = ACTIVE_TASK
    mock.get_environment.return_value = ENV
    mock.delete_environment.return_value = EnvironmentResponse(
        environment_id=ENVIRONMENT_ID, initialized=False
    )
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


def test_get_nonexistant_plan(
    client: BlueapiClient,
):
    with pytest.raises(AttributeError):
        _ = client.plans.fizz_buzz.model


def test_get_devices(client: BlueapiClient):
    assert DeviceResponse(devices=[d.model for d in client.devices]) == DEVICES


def test_get_device(client: BlueapiClient):
    assert client.devices.foo.model == DEVICE


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
    assert foo == "foo"
    x = client.devices.foo.x
    assert x == "foo.x"


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


def test_cannot_run_task_without_message_bus(client: BlueapiClient, mock_rest: Mock):
    mock_rest.get_stomp_config.return_value = None
    with pytest.raises(
        MissingStompConfigurationError,
        match="Stomp configuration required to run plans is missing or disabled",
    ):
        client.run_task(TaskRequest(name="foo", instrument_session="cm12345-1"))


@patch("blueapi.client.client.EventBusClient")
def test_run_task_with_stomp_config_from_server(
    ebc: Mock, client: BlueapiClient, mock_rest: Mock
):
    mock_rest.get_stomp_config.return_value = StompConfig(
        enabled=True, url=TcpUrl("tcp://localhost:9876"), auth=None
    )
    mock_rest.create_task.return_value = TaskResponse(task_id="foo")
    mock_rest.update_worker_task.return_value = TaskResponse(task_id="foo")
    events = MagicMock(spec=EventBusClient, name="EventBusClient")
    ctx = Mock(correlation_id="foo")
    events.subscribe_to_all_events.side_effect = lambda on_event: on_event(
        COMPLETE_EVENT, ctx
    )
    ebc.from_stomp_config.return_value = events

    client.run_task(TaskRequest(name="foo", instrument_session="cm12345-1"))

    mock_rest.get_stomp_config.assert_called_once()


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
    exporter: JsonObjectSpanExporter,
    client: BlueapiClient,
    mock_rest: Mock,
):
    mock_rest.get_stomp_config.return_value = None
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


def test_plan_cache_ignores_underscores(client):
    cache = PlanCache(client, [PlanModel(name="_ignored"), PlanModel(name="used")])
    with pytest.raises(AttributeError, match="_ignored"):
        _ = cache._ignored


def test_plan_cache_repr(client):
    assert repr(client.plans) == "PlanCache(2 plans)"


def test_device_cache_ignores_underscores():
    rest = Mock()
    rest.get_devices.return_value = DeviceResponse(
        devices=[
            DeviceModel(name="_ignored", protocols=[]),
        ]
    )
    cache = DeviceCache(rest)
    with pytest.raises(AttributeError, match="_ignored"):
        _ = cache._ignored

    rest.get_devices.reset_mock()
    with pytest.raises(AttributeError, match="_anything"):
        _ = cache._anything
    rest.get_device.assert_not_called()


def test_devices_are_cached(mock_rest):
    cache = DeviceCache(mock_rest)
    _ = cache.foo
    mock_rest.get_device.assert_not_called()
    _ = cache["foo"]
    mock_rest.get_device.assert_not_called()


def test_device_cache_repr(client):
    assert repr(client.devices) == "DeviceCache(2 devices)"


def test_device_repr():
    cache = Mock()
    model = Mock()
    dev = DeviceRef(name="foo", cache=cache, model=model)
    assert repr(dev) == "Device(foo)"


def test_device_ignores_underscores():
    cache = MagicMock()
    model = Mock()
    dev = DeviceRef(name="foo", cache=cache, model=model)
    with pytest.raises(AttributeError, match="_underscore"):
        _ = dev._underscore
    cache.__getitem__.assert_not_called()


def test_plan_help_text(client):
    plan = Plan("foo", PlanModel(name="foo", description="help for foo"), client)
    assert plan.help_text == "help for foo"


def test_plan_fallback_help_text(client):
    plan = Plan(
        "foo",
        PlanModel(
            name="foo",
            schema={"properties": {"one": {}, "two": {}}, "required": ["one"]},
        ),
        client,
    )
    assert plan.help_text == "Plan foo(one, two=None)"


def test_plan_properties(client):
    plan = Plan(
        "foo",
        PlanModel(
            name="foo",
            schema={"properties": {"one": {}, "two": {}}, "required": ["one"]},
        ),
        client,
    )

    assert plan.properties == {"one", "two"}
    assert plan.required == ["one"]


def test_plan_empty_fallback_help_text(client):
    plan = Plan(
        "foo", PlanModel(name="foo", schema={"properties": {}, "required": []}), client
    )
    assert plan.help_text == "Plan foo()"


p = pytest.param


@pytest.mark.parametrize(
    "args,kwargs,params",
    [
        p((1,), {}, {"one": 1}, id="required_as_positional"),
        p((), {"one": 7}, {"one": 7}, id="required_as_keyword"),
        p((1,), {"two": 23}, {"one": 1, "two": 23}, id="all_as_mixed_args_kwargs"),
        p((1, 2), {}, {"one": 1, "two": 2}, id="all_as_positional"),
        p((), {"one": 21, "two": 42}, {"one": 21, "two": 42}, id="all_as_keyword"),
    ],
)
def test_plan_param_mapping(args, kwargs, params):
    client = Mock()
    client.instrument_session = "cm12345-1"
    plan = Plan(
        FULL_PLAN.name,
        FULL_PLAN,
        client,
    )

    plan(*args, **kwargs)
    client.run_task.assert_called_once_with(
        TaskRequest(name="foobar", instrument_session="cm12345-1", params=params)
    )


@pytest.mark.parametrize(
    "args,kwargs,msg",
    [
        p((), {}, r"Missing argument\(s\) for \{'one'\}", id="missing_required"),
        p((1,), {"one": 7}, "multiple values for one", id="duplicate_required"),
        p((1, 2), {"two": 23}, "multiple values for two", id="duplicate_optional"),
        p((1, 2, 3), {}, "too many arguments", id="too_many_args"),
        p(
            (),
            {"unknown_key": 42},
            r"got unexpected arguments: \{'unknown_key'\}",
            id="unknown_arg",
        ),
    ],
)
def test_plan_invalid_param_mapping(args, kwargs, msg):
    client = Mock()
    client.instrument_session = "cm12345-1"
    plan = Plan(
        FULL_PLAN.name,
        FULL_PLAN,
        client,
    )

    with pytest.raises(TypeError, match=msg):
        plan(*args, **kwargs)
    client.run_task.assert_not_called()


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

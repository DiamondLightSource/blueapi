import itertools
import threading
from concurrent.futures import Future
from typing import Any, Callable, Iterable, List, Optional, TypeVar, Union

import pytest

from blueapi.config import EnvironmentConfig, Source, SourceKind
from blueapi.core import BlueskyContext, EventStream, MsgGenerator
from blueapi.core.bluesky_types import DataEvent
from blueapi.worker import (
    ProgressEvent,
    RunEngineWorker,
    RunPlan,
    Task,
    TaskStatus,
    TrackableTask,
    Worker,
    WorkerBusyError,
    WorkerEvent,
    WorkerState,
)

_SIMPLE_TASK = RunPlan(name="sleep", params={"time": 0.0})
_LONG_TASK = RunPlan(name="sleep", params={"time": 1.0})
_INDEFINITE_TASK = RunPlan(
    name="set_absolute",
    params={"movable": "fake_device", "value": 4.0},
)
_FAILING_TASK = RunPlan(name="failing_plan", params={})


class FakeDevice:
    event: threading.Event

    @property
    def name(self) -> str:
        return "fake_device"

    def __init__(self) -> None:
        self.event = threading.Event()

    def set(self, pos: float) -> None:
        self.event.wait()
        self.event.clear()


def failing_plan() -> MsgGenerator:
    raise KeyError("I failed")


@pytest.fixture
def fake_device() -> FakeDevice:
    return FakeDevice()


@pytest.fixture
def context(fake_device: FakeDevice) -> BlueskyContext:
    ctx = BlueskyContext()
    ctx_config = EnvironmentConfig()
    ctx_config.sources.append(
        Source(kind=SourceKind.DEVICE_FUNCTIONS, module="devices")
    )
    ctx.plan(failing_plan)
    ctx.device(fake_device)
    ctx.with_config(ctx_config)
    return ctx


@pytest.fixture
def inert_worker(context: BlueskyContext) -> Worker[Task]:
    return RunEngineWorker(context, start_stop_timeout=2.0)


@pytest.fixture
def worker(inert_worker: Worker[Task]) -> Iterable[Worker[Task]]:
    inert_worker.start()
    yield inert_worker
    inert_worker.stop()


def test_stop_doesnt_hang(inert_worker: Worker) -> None:
    inert_worker.start()
    inert_worker.stop()


def test_stop_is_idempontent_if_worker_not_started(inert_worker: Worker) -> None:
    inert_worker.stop()


def test_multi_stop(inert_worker: Worker) -> None:
    inert_worker.start()
    inert_worker.stop()
    inert_worker.stop()


def test_restart(inert_worker: Worker) -> None:
    inert_worker.start()
    inert_worker.stop()
    inert_worker.start()
    inert_worker.stop()


def test_multi_start(inert_worker: Worker) -> None:
    inert_worker.start()
    with pytest.raises(Exception):
        inert_worker.start()
    inert_worker.stop()


def test_submit_task(worker: Worker) -> None:
    assert worker.get_pending_tasks() == []
    task_id = worker.submit_task(_SIMPLE_TASK)
    assert worker.get_pending_tasks() == [
        TrackableTask(task_id=task_id, task=_SIMPLE_TASK)
    ]


def test_submit_multiple_tasks(worker: Worker) -> None:
    assert worker.get_pending_tasks() == []
    task_id_1 = worker.submit_task(_SIMPLE_TASK)
    assert worker.get_pending_tasks() == [
        TrackableTask(task_id=task_id_1, task=_SIMPLE_TASK)
    ]
    task_id_2 = worker.submit_task(_LONG_TASK)
    assert worker.get_pending_tasks() == [
        TrackableTask(task_id=task_id_1, task=_SIMPLE_TASK),
        TrackableTask(task_id=task_id_2, task=_LONG_TASK),
    ]


def test_stop_with_task_pending(inert_worker: Worker) -> None:
    inert_worker.start()
    inert_worker.submit_task(_SIMPLE_TASK)
    inert_worker.stop()


def test_restart_leaves_task_pending(worker: Worker) -> None:
    task_id = worker.submit_task(_SIMPLE_TASK)
    assert worker.get_pending_tasks() == [
        TrackableTask(task_id=task_id, task=_SIMPLE_TASK)
    ]
    worker.stop()
    worker.start()
    assert worker.get_pending_tasks() == [
        TrackableTask(task_id=task_id, task=_SIMPLE_TASK)
    ]


def test_submit_before_start_pending(inert_worker: Worker) -> None:
    task_id = inert_worker.submit_task(_SIMPLE_TASK)
    inert_worker.start()
    assert inert_worker.get_pending_tasks() == [
        TrackableTask(task_id=task_id, task=_SIMPLE_TASK)
    ]
    inert_worker.stop()
    assert inert_worker.get_pending_tasks() == [
        TrackableTask(task_id=task_id, task=_SIMPLE_TASK)
    ]


def test_clear_task(worker: Worker) -> None:
    task_id = worker.submit_task(_SIMPLE_TASK)
    assert worker.get_pending_tasks() == [
        TrackableTask(task_id=task_id, task=_SIMPLE_TASK)
    ]
    assert worker.clear_task(task_id)
    assert worker.get_pending_tasks() == []


def test_clear_nonexistant_task(worker: Worker) -> None:
    with pytest.raises(KeyError):
        worker.clear_task("foo")


def test_does_not_allow_simultaneous_running_tasks(
    worker: Worker,
    fake_device: FakeDevice,
) -> None:
    task_ids = [
        worker.submit_task(_INDEFINITE_TASK),
        worker.submit_task(_INDEFINITE_TASK),
    ]
    with pytest.raises(WorkerBusyError):
        for task_id in task_ids:
            worker.begin_task(task_id)
    fake_device.event.set()


def test_begin_task_blocks_until_current_task_set(worker: Worker) -> None:
    task_id = worker.submit_task(_SIMPLE_TASK)
    assert worker.get_active_task() is None
    worker.begin_task(task_id)
    active_task = worker.get_active_task()
    assert active_task is not None
    assert active_task.task == _SIMPLE_TASK


def test_plan_failure_recorded_in_active_task(worker: Worker) -> None:
    task_id = worker.submit_task(_FAILING_TASK)
    events_future: Future[List[WorkerEvent]] = take_events(
        worker.worker_events,
        lambda event: event.task_status is not None and event.task_status.task_failed,
    )
    worker.begin_task(task_id)
    events = events_future.result(timeout=5.0)
    assert events[-1].task_status is not None
    assert events[-1].task_status.task_failed
    assert events[-1].errors == ["'I failed'"]

    active_task = worker.get_active_task()
    assert active_task is not None
    assert active_task.errors == ["'I failed'"]


@pytest.mark.parametrize("num_runs", [0, 1, 2])
def test_produces_worker_events(worker: Worker, num_runs: int) -> None:
    task_ids = [worker.submit_task(_SIMPLE_TASK) for _ in range(num_runs)]
    event_sequences = [_sleep_events(task_id) for task_id in task_ids]

    for task_id, events in zip(task_ids, event_sequences):
        assert_run_produces_worker_events(events, worker, task_id)


def _sleep_events(task_id: str) -> List[WorkerEvent]:
    return [
        WorkerEvent(
            state=WorkerState.RUNNING,
            task_status=TaskStatus(
                task_id=task_id, task_complete=False, task_failed=False
            ),
            errors=[],
            warnings=[],
        ),
        WorkerEvent(
            state=WorkerState.IDLE,
            task_status=TaskStatus(
                task_id=task_id, task_complete=False, task_failed=False
            ),
            errors=[],
            warnings=[],
        ),
        WorkerEvent(
            state=WorkerState.IDLE,
            task_status=TaskStatus(
                task_id=task_id, task_complete=True, task_failed=False
            ),
            errors=[],
            warnings=[],
        ),
    ]


def test_no_additional_progress_events_after_complete(worker: Worker):
    """
    See https://github.com/bluesky/ophyd/issues/1115
    """

    progress_events: List[ProgressEvent] = []
    worker.progress_events.subscribe(lambda event, id: progress_events.append(event))

    task: Task = RunPlan(
        name="move", params={"moves": {"additional_status_device": 5.0}}
    )
    task_id = worker.submit_task(task)
    begin_task_and_wait_until_complete(worker, task_id)

    # Extract all the display_name fields from the events
    list_of_dict_keys = [pe.statuses.values() for pe in progress_events]
    status_views = [item for sublist in list_of_dict_keys for item in sublist]
    display_names = [view.display_name for view in status_views]

    assert "STATUS_AFTER_FINISH" not in display_names


#
# Worker helpers
#


def assert_run_produces_worker_events(
    expected_events: List[WorkerEvent],
    worker: Worker,
    task_id: str,
) -> None:
    assert begin_task_and_wait_until_complete(worker, task_id) == expected_events


def begin_task_and_wait_until_complete(
    worker: Worker,
    task_id: str,
    timeout: float = 5.0,
) -> List[WorkerEvent]:
    events: "Future[List[WorkerEvent]]" = take_events(
        worker.worker_events,
        lambda event: event.is_complete(),
    )

    worker.begin_task(task_id)
    return events.result(timeout=timeout)


#
# Event stream helpers
#


def test_worker_and_data_events_produce_in_order(worker: Worker) -> None:
    assert_running_count_plan_produces_ordered_worker_and_data_events(
        [
            WorkerEvent(
                state=WorkerState.RUNNING,
                task_status=TaskStatus(
                    task_id="count", task_complete=False, task_failed=False
                ),
                errors=[],
                warnings=[],
            ),
            DataEvent(name="start", doc={}),
            DataEvent(name="descriptor", doc={}),
            DataEvent(name="event", doc={}),
            DataEvent(name="stop", doc={}),
            WorkerEvent(
                state=WorkerState.IDLE,
                task_status=TaskStatus(
                    task_id="count", task_complete=False, task_failed=False
                ),
                errors=[],
                warnings=[],
            ),
            WorkerEvent(
                state=WorkerState.IDLE,
                task_status=TaskStatus(
                    task_id="count", task_complete=True, task_failed=False
                ),
                errors=[],
                warnings=[],
            ),
        ],
        worker,
    )


def assert_running_count_plan_produces_ordered_worker_and_data_events(
    expected_events: List[Union[WorkerEvent, DataEvent]],
    worker: Worker,
    task: Task = RunPlan(name="count", params={"detectors": ["image_det"], "num": 1}),
    timeout: float = 5.0,
) -> None:
    event_streams: List[EventStream[Any, int]] = [
        worker.data_events,
        worker.worker_events,
    ]

    count = itertools.count()
    events: "Future[List[Any]]" = take_events_from_streams(
        event_streams,
        lambda _: next(count) >= len(expected_events) - 1,
    )

    task_id = worker.submit_task(task)
    worker.begin_task(task_id)
    results = events.result(timeout=timeout)

    for actual, expected in itertools.zip_longest(results, expected_events):
        if isinstance(expected, WorkerEvent):
            if expected.task_status:
                expected.task_status.task_id = task_id
            assert actual == expected
        elif isinstance(expected, DataEvent):
            assert isinstance(actual, DataEvent)
            assert actual.name == expected.name


E = TypeVar("E")


def take_n_events(
    stream: EventStream[E, Any],
    num: int,
) -> "Future[List[E]]":
    count = itertools.count()
    return take_events(stream, lambda _: next(count) >= num)


def take_events(
    stream: EventStream[E, Any],
    cutoff_predicate: Callable[[E], bool],
) -> "Future[List[E]]":
    events: List[E] = []
    future: "Future[List[E]]" = Future()

    def on_event(event: E, event_id: Optional[str]) -> None:
        events.append(event)
        if cutoff_predicate(event):
            future.set_result(events)

    sub = stream.subscribe(on_event)
    future.add_done_callback(lambda _: stream.unsubscribe(sub))
    return future


def take_events_from_streams(
    streams: List[EventStream[Any, int]],
    cutoff_predicate: Callable[[Any], bool],
) -> "Future[List[Any]]":
    """Returns a collated list of futures for events in numerous event streams.

    The support for generic and algebraic types doesn't appear to extend to
    taking an arbitrary list of concrete types with single but differing
    generic arguments while also maintaining the generality of the argument
    types.

    The type for streams will be any combination of event streams each of a
    given event type, where the event type is generic:

    List[
        Union[
            EventStream[WorkerEvent, int],
            EventStream[DataEvent, int],
            EventStream[ProgressEvent, int]
        ]
    ]

    """
    events: List[Any] = []
    future: "Future[List[Any]]" = Future()

    def on_event(event: Any, event_id: Optional[str]) -> None:
        print(event)
        events.append(event)
        if cutoff_predicate(event):
            future.set_result(events)

    for stream in streams:
        sub = stream.subscribe(on_event)
        future.add_done_callback(lambda _: stream.unsubscribe(sub))
    return future

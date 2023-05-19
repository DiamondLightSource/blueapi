import asyncio
import itertools
from concurrent.futures import Future
from typing import Callable, Iterable, List, Optional, TypeVar

import bluesky.plan_stubs as bps
import pytest

from blueapi.config import EnvironmentConfig, Source, SourceKind
from blueapi.core import BlueskyContext, EventStream, MsgGenerator
from blueapi.worker import (
    RunEngineWorker,
    RunPlan,
    Task,
    TaskStatus,
    Worker,
    WorkerEvent,
    WorkerState,
)
from blueapi.worker.event import ProgressEvent
from blueapi.worker.worker_busy_error import WorkerBusyError

_SIMPLE_TASK = RunPlan(name="sleep", params={"time": 0.0})
_LONG_TASK = RunPlan(name="sleep", params={"time": 1.0})
_INDEFINITE_TASK = RunPlan(name="hang_until_stop", params={})


@pytest.fixture
def stop_plan() -> asyncio.Event:
    return asyncio.Event()


@pytest.fixture
def context(stop_plan: asyncio.Event) -> BlueskyContext:
    def hang_until_stop() -> MsgGenerator:
        yield from bps.wait_for([stop_plan.wait])

    ctx = BlueskyContext()
    ctx_config = EnvironmentConfig()
    ctx_config.sources.append(
        Source(kind=SourceKind.DEVICE_FUNCTIONS, module="devices")
    )
    ctx.with_config(ctx_config)
    ctx.plan(hang_until_stop)
    return ctx


@pytest.fixture
def inert_worker(context: BlueskyContext) -> Worker[Task]:
    return RunEngineWorker(context, stop_timeout=2.0)


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


def test_multi_start(inert_worker: Worker) -> None:
    inert_worker.start()
    with pytest.raises(Exception):
        inert_worker.start()
    inert_worker.stop()


def test_submit_task(worker: Worker) -> None:
    assert worker.get_pending_tasks() == []
    worker.submit_task(_SIMPLE_TASK)
    assert worker.get_pending_tasks() == [_SIMPLE_TASK]


def test_submit_multiple_tasks(worker: Worker) -> None:
    assert worker.get_pending_tasks() == []
    worker.submit_task(_SIMPLE_TASK)
    assert worker.get_pending_tasks() == [_SIMPLE_TASK]
    worker.submit_task(_LONG_TASK)
    assert worker.get_pending_tasks() == [_SIMPLE_TASK, _LONG_TASK]


def test_stop_with_task_pending(inert_worker: Worker) -> None:
    inert_worker.start()
    inert_worker.submit_task(_SIMPLE_TASK)
    inert_worker.stop()


def test_clear_task(worker: Worker) -> None:
    task_id = worker.submit_task(_SIMPLE_TASK)
    assert worker.get_pending_tasks() == [_SIMPLE_TASK]
    worker.clear_task(task_id)
    assert worker.get_pending_tasks() == []


def test_clear_nonexistant_task(worker: Worker) -> None:
    with pytest.raises(KeyError):
        worker.clear_task("foo")


@pytest.mark.parametrize("num_runs", [2, 3, 4])
def test_does_not_allow_simultaneous_running_tasks(
    worker: Worker, stop_plan: asyncio.Event, num_runs: int
) -> None:
    task_ids = [worker.submit_task(_INDEFINITE_TASK) for _ in range(num_runs)]
    with pytest.raises(WorkerBusyError):
        try:
            for task_id in task_ids:
                worker.begin_task(task_id)
        except WorkerBusyError as e:
            raise e
        finally:
            stop_plan.set()


@pytest.mark.parametrize("num_runs", [0, 1, 2, 3])
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
                task_name=task_id, task_complete=False, task_failed=False
            ),
            errors=[],
            warnings=[],
        ),
        WorkerEvent(
            state=WorkerState.IDLE,
            task_status=TaskStatus(
                task_name=task_id, task_complete=False, task_failed=False
            ),
            errors=[],
            warnings=[],
        ),
        WorkerEvent(
            state=WorkerState.IDLE,
            task_status=TaskStatus(
                task_name=task_id, task_complete=True, task_failed=False
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


E = TypeVar("E")
S = TypeVar("S")


def take_n_events(
    stream: EventStream[E, S],
    num: int,
) -> "Future[List[E]]":
    count = itertools.count()
    return take_events(stream, lambda _: next(count) >= num)


def take_events(
    stream: EventStream[E, S],
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

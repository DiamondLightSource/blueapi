import itertools
from concurrent.futures import Future
from typing import Callable, Iterable, List, Optional, TypeVar

import pytest

from blueapi.config import EnvironmentConfig, Source, SourceKind
from blueapi.core import BlueskyContext, EventStream
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
_SLEEP_EVENTS = [
    WorkerEvent(
        state=WorkerState.RUNNING,
        task_status=TaskStatus(
            task_name="test", task_complete=False, task_failed=False
        ),
        errors=[],
        warnings=[],
    ),
    WorkerEvent(
        state=WorkerState.IDLE,
        task_status=TaskStatus(
            task_name="test", task_complete=False, task_failed=False
        ),
        errors=[],
        warnings=[],
    ),
    WorkerEvent(
        state=WorkerState.IDLE,
        task_status=TaskStatus(task_name="test", task_complete=True, task_failed=False),
        errors=[],
        warnings=[],
    ),
]


@pytest.fixture
def context() -> BlueskyContext:
    ctx = BlueskyContext()
    ctx_config = EnvironmentConfig()
    ctx_config.sources.append(
        Source(kind=SourceKind.DEVICE_FUNCTIONS, module="devices")
    )
    ctx.with_config(ctx_config)
    return ctx


@pytest.fixture
def worker(context: BlueskyContext) -> Iterable[Worker[Task]]:
    worker = RunEngineWorker(context)
    yield worker
    worker.stop()


def test_stop_doesnt_hang(worker: Worker) -> None:
    worker.start()


def test_stop_is_idempontent_if_worker_not_started(worker: Worker) -> None:
    ...


def test_multi_stop(worker: Worker) -> None:
    worker.start()
    worker.stop()


def test_multi_start(worker: Worker) -> None:
    worker.start()
    with pytest.raises(Exception):
        worker.start()


def test_create_transaction(worker: Worker) -> None:
    assert worker.get_pending() is None
    worker.begin_transaction(_SIMPLE_TASK)
    assert worker.get_pending() is _SIMPLE_TASK


def test_cannot_create_multiple_transactions(worker: Worker) -> None:
    worker.begin_transaction(_SIMPLE_TASK)
    with pytest.raises(WorkerBusyError):
        worker.begin_transaction(_SIMPLE_TASK)


def test_clear_transaction(worker: Worker) -> None:
    worker.begin_transaction(_SIMPLE_TASK)
    assert worker.get_pending() is _SIMPLE_TASK
    worker.clear_transaction()
    worker.begin_transaction(_LONG_TASK)
    assert worker.get_pending() is _LONG_TASK


def test_clear_nonexistant_transaction(worker: Worker) -> None:
    with pytest.raises(KeyError):
        worker.clear_transaction()


def test_commit_wrong_transaction(worker: Worker) -> None:
    worker.begin_transaction(_SIMPLE_TASK)
    with pytest.raises(KeyError):
        worker.commit_transaction("wrong id")


def test_commit_nonexistant_transaction(worker: Worker) -> None:
    with pytest.raises(KeyError):
        worker.commit_transaction("wrong id")


def test_commit_transaction(worker: Worker) -> None:
    worker.start()

    task_id = worker.begin_transaction(_SIMPLE_TASK)
    assert worker.get_pending() is _SIMPLE_TASK

    events: "Future[List[WorkerEvent]]" = take_events(
        worker.worker_events,
        lambda event: event.is_complete(),
    )
    worker.commit_transaction(task_id)
    result = events.result(timeout=5.0)
    assert result == [
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


def test_runs_plan(worker: Worker) -> None:
    assert_run_produces_worker_events(
        _SLEEP_EVENTS,
        worker,
    )


def submit_task_and_wait_until_complete(
    worker: Worker, task: Task, timeout: float = 5.0
) -> List[WorkerEvent]:
    events: "Future[List[WorkerEvent]]" = take_events(
        worker.worker_events,
        lambda event: event.is_complete(),
    )

    worker.submit_task("test", task)
    return events.result(timeout=timeout)


def assert_run_produces_worker_events(
    expected_events: List[WorkerEvent],
    worker: Worker,
    task: Task = RunPlan(name="sleep", params={"time": 0.0}),
) -> None:
    worker.start()
    assert submit_task_and_wait_until_complete(worker, task) == expected_events


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


def test_worker_only_accepts_one_task_on_queue(worker: Worker):
    worker.start()
    task: Task = RunPlan(name="sleep", params={"time": 1.0})

    worker.submit_task("first_task", task)
    with pytest.raises(WorkerBusyError):
        worker.submit_task("second_task", task)


def test_no_additional_progress_events_after_complete(worker: Worker):
    """
    See https://github.com/bluesky/ophyd/issues/1115
    """
    worker.start()

    progress_events: List[ProgressEvent] = []
    worker.progress_events.subscribe(lambda event, id: progress_events.append(event))

    task: Task = RunPlan(
        name="move", params={"moves": {"additional_status_device": 5.0}}
    )
    submit_task_and_wait_until_complete(worker, task)

    # Exctract all the display_name fields from the events
    list_of_dict_keys = [pe.statuses.values() for pe in progress_events]
    status_views = [item for sublist in list_of_dict_keys for item in sublist]
    display_names = [view.display_name for view in status_views]

    assert "STATUS_AFTER_FINISH" not in display_names

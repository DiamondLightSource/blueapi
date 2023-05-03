import itertools
from concurrent.futures import Future
from typing import Callable, Iterable, List, Optional, TypeVar

import pytest

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
from blueapi.worker.worker_busy_error import WorkerBusyError


@pytest.fixture
def context() -> BlueskyContext:
    ctx = BlueskyContext()
    ctx.with_startup_script("blueapi.startup.example")
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


def test_runs_plan(worker: Worker) -> None:
    assert_run_produces_worker_events(
        [
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
                task_status=TaskStatus(
                    task_name="test", task_complete=True, task_failed=False
                ),
                errors=[],
                warnings=[],
            ),
        ],
        worker,
    )


def assert_run_produces_worker_events(
    expected_events: List[WorkerEvent],
    worker: Worker,
    task: Task = RunPlan(name="sleep", params={"time": 0.0}),
    timeout: float = 5.0,
) -> None:
    worker.start()

    events: "Future[List[WorkerEvent]]" = take_events(
        worker.worker_events,
        lambda event: event.is_complete(),
    )
    worker.submit_task("test", task)
    result = events.result(timeout=timeout)
    assert result == expected_events


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

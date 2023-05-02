import itertools
from concurrent.futures import Future
from threading import Event
from typing import Callable, List, TypeVar

import pytest

from blueapi.core import BlueskyContext, EventStream
from blueapi.worker import (
    RunEngineWorker,
    RunPlan,
    Task,
    Worker,
    WorkerEvent,
    WorkerState,
)


@pytest.fixture
def context() -> BlueskyContext:
    ctx = BlueskyContext()
    ctx.with_startup_script("blueapi.startup.example")
    return ctx


@pytest.fixture
def worker(context: BlueskyContext) -> Worker[Task]:
    worker = RunEngineWorker(context)
    yield worker
    worker.stop()


def test_stop_doesnt_hang(worker: Worker) -> None:
    worker.start()


def test_stop_is_idempotent(worker: Worker) -> None:
    ...


def test_multi_stop(worker: Worker) -> None:
    worker.start()
    worker.stop()


def test_multi_start(worker: Worker) -> None:
    worker.start()
    with pytest.raises(Exception):
        worker.start()


def test_submit(worker: Worker) -> None:
    worker.start()

    events: "Future[List[WorkerEvent]]" = take_n_events(
        worker.worker_events,
        1,
    )
    worker.submit_task(
        "test",
        RunPlan(
            name="sleep",
            params={"time": 0.0},
        ),
    )
    result = events.result(timeout=5.0)[0]
    assert not result.errors
    assert result.state is WorkerState.RUNNING


def test_submit_invalid_task(worker: Worker[Task]) -> None:
    worker.start()

    with pytest.raises(Exception):
        worker.submit_task(
            "test",
            123,
        )


@pytest.mark.parametrize(
    "test_name, plan",
    [
        ("test1", {"name": "sleep", "params": {"time": 0.1}}),
        ("test2", {"name": "sleep", "params": {"time": 0.2}}),
        ("test3", {"name": "sleep", "params": {"time": 0.3}}),
        ("test4", {"name": "sleep", "params": {"time": 0.4}}),
    ],
)
def test_submit_multiple_tasks_at_once(
    test_name: str, plan: RunPlan, worker: Worker[Task]
):
    worker.start()
    started: Future[WorkerEvent] = Future()

    def process_event(event: WorkerEvent, task_id: str) -> None:
        started.set_result(event)

    worker.worker_events.subscribe(process_event)
    worker.submit_task(
        test_name,
        RunPlan(**plan),
    )
    result = started.result(timeout=plan["params"]["time"])
    assert not result.errors
    assert result.state is WorkerState.RUNNING


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

    def on_event(event: E, event_id: str) -> None:
        events.append(event)
        if cutoff_predicate(event):
            future.set_result(events)

    sub = stream.subscribe(on_event)
    future.add_done_callback(lambda _: stream.unsubscribe(sub))
    return future

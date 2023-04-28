from concurrent.futures import Future

import pytest

from blueapi.core import BlueskyContext
from blueapi.worker import (
    RunEngineWorker,
    RunPlan,
    Worker,
    WorkerEvent,
    WorkerState,
    Task,
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


def test_stop(worker: Worker) -> None:
    worker.start()


def test_submit(worker: Worker) -> None:
    worker.start()
    started: Future[WorkerEvent] = Future()

    def process_event(event: WorkerEvent, task_id: str) -> None:
        started.set_result(event)

    worker.worker_events.subscribe(process_event)
    worker.submit_task(
        "test",
        RunPlan(
            name="sleep",
            params={"time": 0.1},
        ),
    )
    result = started.result(timeout=5.0)
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

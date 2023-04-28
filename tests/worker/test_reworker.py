from concurrent.futures import Future
from threading import Event

import pytest

from blueapi.core import BlueskyContext
from blueapi.worker import RunEngineWorker, RunPlan, Worker, WorkerEvent, WorkerState


@pytest.fixture
def context() -> BlueskyContext:
    ctx = BlueskyContext()
    ctx.with_startup_script("blueapi.startup.example")
    return ctx


@pytest.fixture
def worker(context: BlueskyContext) -> Worker:
    worker = RunEngineWorker(context)
    yield worker
    worker.stop()


def test_stop(worker: Worker) -> None:
    worker.start()


def test_submit(worker: Worker) -> None:
    worker.start()
    started = Future()

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
    assert started.result(timeout=5.0).status.state is WorkerState.RUNNING

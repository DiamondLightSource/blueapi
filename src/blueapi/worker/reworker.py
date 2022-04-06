import logging
from queue import Queue
from typing import Callable, List, Optional

from bluesky import RunEngine

from blueapi.core import EventStream, EventStreamBase

from .event import RawRunEngineState, RunnerState, WorkerEvent
from .task import Task, TaskContext
from .worker import Worker

LOGGER = logging.getLogger(__name__)


class RunEngineWorker(Worker[Task]):
    """
    Worker wrapping RunEngine that can work in its own thread/process

    :param run_engine: The RunEngine to wrap
    :param loop: The event loop of any services communicating with the worker.
    """

    _run_engine: RunEngine
    _task_queue: Queue  # type: ignore
    _current_task: Optional[Task]
    _worker_events: EventStream

    def __init__(
        self,
        run_engine: RunEngine,
    ) -> None:
        self._run_engine = run_engine
        self._task_queue = Queue()
        self._current_task = None
        self._worker_events = EventStream()

    def submit_task(self, task: Task) -> None:
        LOGGER.info(f"Submitting: {task}")
        self._task_queue.put(task)

    def run_forever(self) -> None:
        self._run_engine.state_hook = self._on_state_change

        while True:
            self._cycle()

    def _cycle(self) -> None:
        next_task: Task = self._task_queue.get()
        self._current_task = next_task  # Informing mypy that the task is not None
        ctx = TaskContext(self._run_engine)
        self._current_task.do_task(ctx)

    @property
    def worker_events(self) -> EventStreamBase[WorkerEvent, int]:
        return self.worker_events

    def _on_state_change(
        self,
        raw_new_state: RawRunEngineState,
        raw_old_state: Optional[RawRunEngineState] = None,
    ) -> None:
        new_state = RunnerState.from_bluesky_state(raw_new_state)
        if raw_old_state:
            old_state = RunnerState.from_bluesky_state(raw_old_state)
        else:
            old_state = RunnerState.UNKNOWN
        LOGGER.debug(f"Notifying state change {old_state} -> {new_state}")
        self._worker_events.notify(WorkerEvent(self._current_task, new_state))

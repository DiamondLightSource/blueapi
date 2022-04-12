import logging
from queue import Queue
from typing import Callable, List, Optional

from blueapi.core import BlueskyContext

from .event import RawRunEngineState, RunnerState, WorkerEvent
from .task import Task
from .worker import Worker

LOGGER = logging.getLogger(__name__)


class RunEngineWorker(Worker[Task]):
    """
    Worker wrapping RunEngine that can work in its own thread/process

    :param run_engine: The RunEngine to wrap
    :param loop: The event loop of any services communicating with the worker.
    """

    _ctx: BlueskyContext
    _task_queue: Queue  # type: ignore
    _current_task: Optional[Task]
    _subscribers: List[Callable[[WorkerEvent], None]]

    def __init__(
        self,
        ctx: BlueskyContext,
    ) -> None:
        self._ctx = ctx
        self._task_queue = Queue()
        self._current_task = None
        self._subscribers = []

    def submit_task(self, task: Task) -> None:
        LOGGER.info(f"Submitting: {task}")
        self._task_queue.put(task)

    def run_forever(self) -> None:
        LOGGER.info("Worker starting")
        self._ctx.run_engine.state_hook = self._on_state_change

        while True:
            self._cycle()

    def _cycle(self) -> None:
        LOGGER.info("Awaiting task")
        next_task: Task = self._task_queue.get()
        LOGGER.info(f"Got new task: {next_task}")
        self._current_task = next_task  # Informing mypy that the task is not None
        self._current_task.do_task(self._ctx)

    def subscribe(self, callback: Callable[[WorkerEvent], None]) -> int:
        self._subscribers.append(callback)
        return len(self._subscribers) - 1

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
        self._notify(WorkerEvent(self._current_task, new_state))

    def _notify(self, event: WorkerEvent) -> None:
        for callback in self._subscribers:
            callback(event)

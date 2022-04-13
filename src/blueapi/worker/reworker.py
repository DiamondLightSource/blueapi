import logging
from queue import Queue
from typing import Optional

from blueapi.core import BlueskyContext, EventPublisher, EventStream

from .event import RawRunEngineState, RunnerState, TaskEvent, WorkerEvent
from .task import ActiveTask, Task, TaskState
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
    _current: Optional[ActiveTask]

    _worker_events: EventPublisher[WorkerEvent]
    _task_events: EventPublisher[TaskEvent]

    def __init__(
        self,
        ctx: BlueskyContext,
    ) -> None:
        self._ctx = ctx
        self._task_queue = Queue()
        self._current = None
        self._worker_events = EventPublisher()
        self._task_events = EventPublisher()

    def submit_task(self, name: str, task: Task) -> None:
        active_task = ActiveTask(name, task)
        LOGGER.info(f"Submitting: {active_task}")
        self._task_events.publish(TaskEvent(active_task))
        self._task_queue.put(active_task)

    def run_forever(self) -> None:
        LOGGER.info("Worker starting")
        self._ctx.run_engine.state_hook = self._on_state_change

        while True:
            self._cycle()

    def _cycle(self) -> None:
        LOGGER.info("Awaiting task")
        next_task: ActiveTask = self._task_queue.get()
        LOGGER.info(f"Got new task: {next_task}")
        self._current = next_task  # Informing mypy that the task is not None
        self._set_task_state(TaskState.RUNNING)
        self._current.task.do_task(self._ctx)
        self._set_task_state(TaskState.COMPLETE)

    @property
    def worker_events(self) -> EventStream[WorkerEvent, int]:
        return self._worker_events

    @property
    def task_events(self) -> EventStream[TaskEvent, int]:
        return self._task_events

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
        if self._current is not None:
            name = self._current.name
        else:
            name = None
        self._worker_events.publish(WorkerEvent(new_state, name))

    def _set_task_state(self, state: TaskState, error: Optional[str] = None) -> None:
        if self._current is None:
            raise ValueError("Cannot set task state when we are not running a task!")
        self._current.state = state
        self._task_events.publish(TaskEvent(self._current, error))

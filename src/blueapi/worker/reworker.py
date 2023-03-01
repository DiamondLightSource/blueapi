import logging
import uuid
from functools import partial
from queue import Queue
from threading import RLock
from typing import Any, Dict, Iterable, Mapping, Optional

from bluesky.protocols import Status

from blueapi.core import (
    BlueskyContext,
    DataEvent,
    EventPublisher,
    EventStream,
    WatchableStatus,
)

from .event import (
    RawRunEngineState,
    RunnerState,
    StatusEvent,
    StatusView,
    TaskEvent,
    WorkerEvent,
    WorkerStatusEvent,
)
from .task import ActiveTask, Task, TaskState
from .worker import Worker

LOGGER = logging.getLogger(__name__)


class RunEngineWorker(Worker[Task]):
    """
    Worker wrapping BlueskyContext that can work in its own thread/process

    Args:
        ctx (BlueskyContext): Context to work with
    """

    _ctx: BlueskyContext
    _task_queue: Queue  # type: ignore
    _current: Optional[ActiveTask]
    _status_lock: RLock
    _status_snapshot: Dict[str, StatusView]

    _worker_events: EventPublisher[WorkerEvent]
    _data_events: EventPublisher[DataEvent]

    def __init__(
        self,
        ctx: BlueskyContext,
    ) -> None:
        self._ctx = ctx
        self._task_queue = Queue()
        self._current = None
        self._worker_events = EventPublisher()
        self._data_events = EventPublisher()
        self._status_lock = RLock()
        self._status_snapshot = {}

    def submit_task(self, name: str, task: Task) -> None:
        active_task = ActiveTask(name, task)
        LOGGER.info(f"Submitting: {active_task}")
        self._task_queue.put(active_task)
        self._worker_events.publish(TaskEvent(active_task.state, active_task.name))

    def run_forever(self) -> None:
        LOGGER.info("Worker starting")
        self._ctx.run_engine.state_hook = self._on_state_change
        self._ctx.run_engine.subscribe(self._on_document)
        self._ctx.run_engine.waiting_hook = self._waiting_hook

        while True:
            self._cycle_with_error_handling()

    def _cycle_with_error_handling(self) -> None:
        try:
            self._cycle()
        except Exception as ex:
            self._report_error(ex)

    def _cycle(self) -> None:
        LOGGER.info("Awaiting task")
        next_task: ActiveTask = self._task_queue.get()
        LOGGER.info(f"Got new task: {next_task}")
        self._current = next_task  # Informing mypy that the task is not None
        self._set_task_state(TaskState.RUNNING)
        self._current.task.do_task(self._ctx)
        self._set_task_state(TaskState.COMPLETE)
        self._current = None

    @property
    def worker_events(self) -> EventStream[WorkerEvent, int]:
        return self._worker_events

    @property
    def data_events(self) -> EventStream[DataEvent, int]:
        return self._data_events

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
        self._report_worker_state(new_state)

    def _report_error(self, err: Exception) -> None:
        LOGGER.error(err, exc_info=True)
        self._set_task_state(TaskState.FAILED, str(err))

    def _panic(self, error: Optional[str] = None) -> None:
        self._report_worker_state(RunnerState.PANICKED, error)

    def _report_worker_state(
        self, state: RunnerState, error: Optional[str] = None
    ) -> None:
        self._worker_events.publish(WorkerStatusEvent(state, error))

    def _set_task_state(self, state: TaskState, error: Optional[str] = None) -> None:
        if self._current is not None:
            self._current.state = state
            event = TaskEvent(
                self._current.state, self._current.name, error_message=error
            )
            self._worker_events.publish(event)
        else:
            error = error or "UNKNOWN ERROR"
            self._panic(
                f"An error occurred while the worker was not running a task: {error}"
            )

    def _on_document(self, name: str, document: Mapping[str, Any]) -> None:
        self._data_events.publish(DataEvent(name, document))

    def _waiting_hook(self, statuses: Optional[Iterable[Status]]) -> None:
        if statuses is not None:
            with self._status_lock:
                for status in statuses:
                    self._monitor_status(status)

    def _monitor_status(self, status: Status) -> None:
        status_name = str(uuid.uuid1())

        if isinstance(status, WatchableStatus) and not status.done:
            LOGGER.info(f"Watching new status: {status_name}")
            self._status_snapshot[status_name] = StatusView()
            status.watch(partial(self._on_status_event, status, status_name))

            # TODO: Maybe introduce an initial event, in which case move
            # all of this code out of the if statement
            def on_complete(status: Status) -> None:
                self._on_status_event(status, status_name)
                del self._status_snapshot[status_name]

            status.add_callback(on_complete)  # type: ignore

    def _on_status_event(
        self,
        status: Status,
        status_name: str,
        *,
        name: Optional[str] = None,
        current: Optional[float] = None,
        initial: Optional[float] = None,
        target: Optional[float] = None,
        unit: Optional[str] = None,
        precision: Optional[int] = None,
        fraction: Optional[float] = None,
        time_elapsed: Optional[float] = None,
        time_remaining: Optional[float] = None,
    ) -> None:
        if not status.done:
            percentage = float(1.0 - fraction) if fraction is not None else None
        else:
            percentage = 1.0
        view = StatusView(
            name or "UNKNOWN",
            current,
            initial,
            target,
            unit or "units",
            precision or 3,
            status.done,
            percentage,
            time_elapsed,
            time_remaining,
        )
        self._status_snapshot[status_name] = view
        self._publish_status_snapshot()

    def _publish_status_snapshot(self) -> None:
        if self._current is None:
            raise ValueError("Got a status update without an active task!")
        else:
            self._worker_events.publish(
                StatusEvent(
                    self._current.name,
                    statuses=self._status_snapshot,
                )
            )

import logging
import uuid
from functools import partial
from queue import Queue
from threading import RLock
from typing import Any, Dict, Iterable, List, Mapping, Optional

from bluesky.protocols import Status

from blueapi.core import (
    BlueskyContext,
    DataEvent,
    EventPublisher,
    EventStream,
    WatchableStatus,
)

from .event import (
    ProgressEvent,
    RawRunEngineState,
    StatusView,
    TaskStatus,
    WorkerEvent,
    WorkerState,
)
from .task import ActiveTask, Task
from .worker import Worker

LOGGER = logging.getLogger(__name__)


class RunEngineWorker(Worker[Task]):
    """
    Worker wrapping BlueskyContext that can work in its own thread/process

    Args:
        ctx (BlueskyContext): Context to work with
    """

    _ctx: BlueskyContext
    _state: WorkerState
    _errors: List[str]
    _warnings: List[str]
    _task_queue: Queue  # type: ignore
    _current: Optional[ActiveTask]
    _status_lock: RLock
    _status_snapshot: Dict[str, StatusView]
    _worker_events: EventPublisher[WorkerEvent]
    _progress_events: EventPublisher[ProgressEvent]
    _data_events: EventPublisher[DataEvent]

    def __init__(
        self,
        ctx: BlueskyContext,
    ) -> None:
        self._ctx = ctx
        self._state = WorkerState.from_bluesky_state(ctx.run_engine.state)
        self._errors = []
        self._warnings = []
        self._task_queue = Queue()
        self._current = None
        self._worker_events = EventPublisher()
        self._progress_events = EventPublisher()
        self._data_events = EventPublisher()
        self._status_lock = RLock()
        self._status_snapshot = {}

    def submit_task(self, name: str, task: Task) -> None:
        active_task = ActiveTask(name, task)
        LOGGER.info(f"Submitting: {active_task}")
        self._task_queue.put(active_task)

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
        try:
            LOGGER.info("Awaiting task")
            next_task: ActiveTask = self._task_queue.get()
            LOGGER.info(f"Got new task: {next_task}")
            self._current = next_task  # Informing mypy that the task is not None
            self._current.task.do_task(self._ctx)
        except Exception as err:
            self._report_error(err)

        if self._current is not None:
            self._current.is_complete = True
        self._report_status()
        self._errors.clear()
        self._warnings.clear()

    @property
    def worker_events(self) -> EventStream[WorkerEvent, int]:
        return self._worker_events

    @property
    def progress_events(self) -> EventStream[ProgressEvent, int]:
        return self._progress_events

    @property
    def data_events(self) -> EventStream[DataEvent, int]:
        return self._data_events

    def _on_state_change(
        self,
        raw_new_state: RawRunEngineState,
        raw_old_state: Optional[RawRunEngineState] = None,
    ) -> None:
        new_state = WorkerState.from_bluesky_state(raw_new_state)
        if raw_old_state:
            old_state = WorkerState.from_bluesky_state(raw_old_state)
        else:
            old_state = WorkerState.UNKNOWN
        LOGGER.debug(f"Notifying state change {old_state} -> {new_state}")
        self._state = new_state
        self._report_status()

    def _report_error(self, err: Exception) -> None:
        LOGGER.error(err, exc_info=True)
        if self._current is not None:
            self._current.is_error = True
        self._errors.append(str(err))

    def _report_status(
        self,
    ) -> None:
        task_status: Optional[TaskStatus]
        errors = self._errors
        warnings = self._warnings
        if self._current is not None:
            task_status = TaskStatus(
                task_name=self._current.name,
                task_complete=self._current.is_complete,
                task_failed=self._current.is_error or bool(errors),
            )
            correlation_id = self._current.name
        else:
            task_status = None
            correlation_id = None

        event = WorkerEvent(
            state=self._state,
            task_status=task_status,
            errors=errors,
            warnings=warnings,
        )
        self._worker_events.publish(event, correlation_id)

    def _on_document(self, name: str, document: Mapping[str, Any]) -> None:
        if self._current is not None:
            correlation_id = self._current.name
            self._data_events.publish(
                DataEvent(name=name, doc=document), correlation_id
            )
        else:
            raise KeyError(
                "Trying to emit a document despite the fact that the RunEngine is idle"
            )

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
            display_name=name or "UNKNOWN",
            current=current,
            initial=initial,
            target=target,
            unit=unit or "units",
            precision=precision or 3,
            done=status.done,
            percentage=percentage,
            time_elapsed=time_elapsed,
            time_remaining=time_remaining,
        )
        self._status_snapshot[status_name] = view
        self._publish_status_snapshot()

    def _publish_status_snapshot(self) -> None:
        if self._current is None:
            raise ValueError("Got a status update without an active task!")
        else:
            self._progress_events.publish(
                ProgressEvent(
                    task_name=self._current.name,
                    statuses=self._status_snapshot,
                ),
                self._current.name,
            )

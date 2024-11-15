import logging
import uuid
from collections.abc import Iterable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from queue import Full, Queue
from threading import Event, RLock
from typing import Any, Generic, TypeVar

from bluesky.protocols import Status
from observability_utils.tracing import (
    add_span_attributes,
    get_tracer,
    setup_tracing,
    start_as_current_span,
)
from opentelemetry.baggage import get_baggage
from opentelemetry.context import Context, get_current
from opentelemetry.trace import SpanKind
from pydantic import Field
from super_state_machine.errors import TransitionError

from blueapi.core import (
    OTLP_EXPORT_ENABLED,
    BlueskyContext,
    DataEvent,
    EventPublisher,
    EventStream,
    WatchableStatus,
)
from blueapi.core.bluesky_event_loop import configure_bluesky_event_loop
from blueapi.utils.base_model import BlueapiBaseModel
from blueapi.utils.thread_exception import handle_all_exceptions

from .event import (
    ProgressEvent,
    RawRunEngineState,
    StatusView,
    TaskStatus,
    TaskStatusEnum,
    WorkerEvent,
    WorkerState,
)
from .task import Task
from .worker_errors import WorkerAlreadyStartedError, WorkerBusyError

LOGGER = logging.getLogger(__name__)
TRACER = get_tracer("task_worker")
""" Initialise a Tracer for this module provided by the app's global TracerProvider. """

DEFAULT_START_STOP_TIMEOUT: float = 30.0
WORKER_THREAD_STATE = "worker thread state"

T = TypeVar("T")


class TrackableTask(BlueapiBaseModel, Generic[T]):
    """
    A representation of a task that the worker recognizes
    """

    task_id: str
    task: T
    request_id: str = ""
    is_complete: bool = False
    is_pending: bool = True
    errors: list[str] = Field(default_factory=list)


class TaskWorker:
    """
    Worker wrapping BlueskyContext that can work in its own thread/process

    Args:
        ctx: Context to work with
        stop_timeout: If the worker is told to stop, number of seconds to wait for
            graceful shutdown before raising an exception. Defaults to 30.0.
    """

    _ctx: BlueskyContext
    _start_stop_timeout: float

    _tasks: dict[str, TrackableTask]

    _state: WorkerState
    _errors: list[str]
    _warnings: list[str]
    _task_channel: Queue  # type: ignore
    _current: TrackableTask | None
    _status_lock: RLock
    _status_snapshot: dict[str, StatusView]
    _completed_statuses: set[str]
    _worker_events: EventPublisher[WorkerEvent]
    _progress_events: EventPublisher[ProgressEvent]
    _data_events: EventPublisher[DataEvent]
    _started: Event
    _stopping: Event
    _stopped: Event
    _current_task_otel_context: Context | None

    def __init__(
        self,
        ctx: BlueskyContext,
        start_stop_timeout: float = DEFAULT_START_STOP_TIMEOUT,
        broadcast_statuses: bool = True,
    ) -> None:
        self._ctx = ctx
        self._start_stop_timeout = start_stop_timeout

        self._tasks = {}

        self._state = WorkerState.from_bluesky_state(ctx.run_engine.state)
        self._errors = []
        self._warnings = []
        self._task_channel = Queue(maxsize=1)
        self._current = None
        self._worker_events = EventPublisher()
        self._progress_events = EventPublisher()
        self._data_events = EventPublisher()
        self._status_lock = RLock()
        self._status_snapshot = {}
        self._completed_statuses = set()
        self._started = Event()
        self._stopping = Event()
        self._stopped = Event()
        self._stopped.set()
        self._broadcast_statuses = broadcast_statuses
        self._current_task_otel_context = None
        setup_tracing("BlueAPIWorker", OTLP_EXPORT_ENABLED)

    @start_as_current_span(TRACER, "task_id")
    def clear_task(self, task_id: str) -> str:
        task = self._tasks.pop(task_id)
        return task.task_id

    @start_as_current_span(TRACER)
    def cancel_active_task(
        self,
        failure: bool = False,
        reason: str | None = None,
    ) -> str:
        if self._current is None:
            # Persuades mypy that self._current is not None
            # We only allow this method to be called if a Plan is active
            raise TransitionError("Attempted to cancel while no active Task")
        if failure:
            self._ctx.run_engine.abort(reason)
            add_span_attributes({"Task aborted": reason})
        else:
            self._ctx.run_engine.stop()
            add_span_attributes({"Task stopped": reason})
        return self._current.task_id

    @start_as_current_span(TRACER)
    def get_tasks(self) -> list[TrackableTask]:
        return list(self._tasks.values())

    @start_as_current_span(TRACER, "task_id")
    def get_task_by_id(self, task_id: str) -> TrackableTask | None:
        return self._tasks.get(task_id)

    @start_as_current_span(TRACER, "status")
    def get_tasks_by_status(self, status: TaskStatusEnum) -> list[TrackableTask]:
        if status == TaskStatusEnum.RUNNING:
            return [
                task
                for task in self._tasks.values()
                if not task.is_pending and not task.is_complete
            ]
        elif status == TaskStatusEnum.PENDING:
            return [task for task in self._tasks.values() if task.is_pending]
        elif status == TaskStatusEnum.COMPLETE:
            return [task for task in self._tasks.values() if task.is_complete]
        return []

    @start_as_current_span(TRACER)
    def get_active_task(self) -> TrackableTask[Task] | None:
        current = self._current
        if current is not None:
            add_span_attributes({"Active Task": current.task_id})
        return current

    @start_as_current_span(TRACER, "task_id")
    def begin_task(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if task is not None:
            self._submit_trackable_task(task)
        else:
            raise KeyError(f"No pending task with ID {task_id}")

    @start_as_current_span(TRACER, "task.name", "task.params")
    def submit_task(self, task: Task) -> str:
        task.prepare_params(self._ctx)  # Will raise if parameters are invalid
        task_id: str = str(uuid.uuid4())
        add_span_attributes({"TaskId": task_id})
        trackable_task = TrackableTask(
            task_id=task_id, request_id=str(get_baggage("correlation_id")), task=task
        )
        self._tasks[task_id] = trackable_task
        return task_id

    @start_as_current_span(
        TRACER,
        "trackable_task.task_id",
        "trackable_task.task.name",
        "trackable_task.task.params",
    )
    def _submit_trackable_task(self, trackable_task: TrackableTask) -> None:
        if self.state is not WorkerState.IDLE:
            raise WorkerBusyError(f"Worker is in state {self.state}")

        task_started = Event()

        def mark_task_as_started(event: WorkerEvent, _: str | None) -> None:
            if (
                event.task_status is not None
                and event.task_status.task_id == trackable_task.task_id
            ):
                task_started.set()

        LOGGER.info(f"Submitting: {trackable_task}")
        try:
            self._current_task_otel_context = get_current()
            sub = self.worker_events.subscribe(mark_task_as_started)
            """ Cache the current trace context as the one for this task id """
            self._task_channel.put_nowait(trackable_task)
            task_started.wait(timeout=5.0)
            if not task_started.is_set():
                raise TimeoutError("Failed to start plan within timeout")
        except Full as f:
            LOGGER.error("Cannot submit task while another is running")
            raise WorkerBusyError("Cannot submit task while another is running") from f
        finally:
            self.worker_events.unsubscribe(sub)

    @start_as_current_span(TRACER)
    def start(self) -> None:
        if self._started.is_set():
            raise WorkerAlreadyStartedError("Worker is already running")
        self._wait_until_stopped()
        run_worker_in_own_thread(self)
        self._wait_until_started()

    @start_as_current_span(TRACER)
    def stop(self) -> None:
        LOGGER.info("Attempting to stop worker")

        # If the worker has not yet started there is nothing to do.
        if self._started.is_set():
            self._task_channel.put(KillSignal())
        else:
            LOGGER.info("Stopping worker: nothing to do")
        self._wait_until_stopped()
        add_span_attributes({WORKER_THREAD_STATE: "STOPPED"})
        LOGGER.info("Stopped")

    @start_as_current_span(TRACER)
    def _wait_until_started(self) -> None:
        if not self._started.wait(timeout=self._start_stop_timeout):
            raise TimeoutError(
                f"Worker did not start within {self._start_stop_timeout} seconds"
            )

    @start_as_current_span(TRACER)
    def _wait_until_stopped(self) -> None:
        if not self._stopped.wait(timeout=self._start_stop_timeout):
            raise TimeoutError(
                f"Worker did not stop within {self._start_stop_timeout} seconds"
            )

    @property
    def state(self) -> WorkerState:
        return self._state

    @start_as_current_span(TRACER)
    def run(self) -> None:
        LOGGER.info("Worker starting")
        self._ctx.run_engine.state_hook = self._on_state_change
        self._ctx.run_engine.subscribe(self._on_document)
        if self._broadcast_statuses:
            self._ctx.run_engine.waiting_hook = self._waiting_hook

        self._stopped.clear()
        self._started.set()
        while not self._stopping.is_set():
            self._cycle_with_error_handling()
        self._started.clear()
        self._stopping.clear()
        self._stopped.set()

    @start_as_current_span(TRACER, "defer")
    def pause(self, defer=False):
        LOGGER.info("Requesting to pause the worker")
        self._ctx.run_engine.request_pause(defer)

    @start_as_current_span(TRACER)
    def resume(self):
        LOGGER.info("Requesting to resume the worker")
        self._ctx.run_engine.resume()

    @start_as_current_span(TRACER)
    def _cycle_with_error_handling(self) -> None:
        try:
            self._cycle()
        except Exception as ex:
            self._report_error(ex)

    @start_as_current_span(TRACER)
    def _cycle(self) -> None:
        try:
            LOGGER.info("Awaiting task")
            next_task: TrackableTask | KillSignal = self._task_channel.get()
            if isinstance(next_task, TrackableTask):
                if self._current_task_otel_context is not None:
                    with TRACER.start_as_current_span(
                        "_cycle",
                        context=self._current_task_otel_context,
                        kind=SpanKind.SERVER,
                    ):
                        LOGGER.info(f"Got new task: {next_task}")
                        self._current = (
                            next_task  # Informing mypy that the task is not None
                        )

                        self._current_task_otel_context = get_current()
                        add_span_attributes({"next_task.task_id": next_task.task_id})

                        self._current.is_pending = False
                        self._current.task.do_task(self._ctx)
            elif isinstance(next_task, KillSignal):
                # If we receive a kill signal we begin to shut the worker down.
                # Note that the kill signal is explicitly not a type of task as we don't
                # want it to be part of the worker's public API
                self._stopping.set()
                add_span_attributes({"server shutting down": "true"})
            else:
                raise KeyError(f"Unknown command: {next_task}")
        except Exception as err:
            self._report_error(err)
        finally:
            if self._current_task_otel_context is not None:
                self._current_task_otel_context = None

        if self._current is not None:
            self._current.is_complete = True
        self._report_status()
        self._errors.clear()
        self._warnings.clear()
        self._completed_statuses.clear()

    @property
    def worker_events(self) -> EventStream[WorkerEvent, int]:
        return self._worker_events

    @property
    def progress_events(self) -> EventStream[ProgressEvent, int]:
        return self._progress_events

    @property
    def data_events(self) -> EventStream[DataEvent, int]:
        return self._data_events

    @start_as_current_span(TRACER, "raw_new_state", "raw_old_state")
    def _on_state_change(
        self,
        raw_new_state: RawRunEngineState,
        raw_old_state: RawRunEngineState | None = None,
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
            self._current.errors.append(str(err))
        self._errors.append(str(err))

    @start_as_current_span(TRACER)
    def _report_status(
        self,
    ) -> None:
        task_status: TaskStatus | None
        errors = self._errors
        warnings = self._warnings
        if self._current is not None:
            task_status = TaskStatus(
                task_id=self._current.task_id,
                task_complete=self._current.is_complete,
                task_failed=bool(self._current.errors),
            )
            correlation_id = self._current.task_id
            add_span_attributes(
                {
                    "task_id": self._current.task_id,
                    "task_complete": self._current.is_complete,
                    "task_failed": self._current.errors,
                }
            )
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
            if self._current_task_otel_context is not None:
                with TRACER.start_as_current_span(
                    "_on_document",
                    context=self._current_task_otel_context,
                    kind=SpanKind.PRODUCER,
                ):
                    """
                    Start a new span but inject the context cached when the current task
                    was created. This will make the documents received part of the same
                    trace.
                    """
                    add_span_attributes(
                        {
                            "task_id": self._current.task_id,
                            "name": name,
                            "document": str(document),
                        }
                    )

                    correlation_id = self._current.request_id
                    self._data_events.publish(
                        DataEvent(name=name, doc=document), correlation_id
                    )
            else:
                raise ValueError(
                    "There is no context set for tracing despite the fact that a task"
                    " is running, something has gone wrong..."
                )

        else:
            raise KeyError(
                "Trying to emit a document despite the fact that the RunEngine is idle"
            )

    def _waiting_hook(self, statuses: Iterable[Status] | None) -> None:
        if statuses is not None:
            with self._status_lock:
                for status in statuses:
                    self._monitor_status(status)

    def _monitor_status(self, status: Status) -> None:
        status_uuid = str(uuid.uuid4())

        if isinstance(status, WatchableStatus) and not status.done:
            LOGGER.info(f"Watching new status: {status_uuid}")
            self._status_snapshot[status_uuid] = StatusView()
            status.watch(partial(self._on_status_event, status, status_uuid))

            # TODO: Maybe introduce an initial event, in which case move
            # all of this code out of the if statement
            def on_complete(status: Status) -> None:
                self._on_status_event(status, status_uuid)
                del self._status_snapshot[status_uuid]
                self._completed_statuses.add(status_uuid)

            status.add_callback(on_complete)  # type: ignore

    def _on_status_event(
        self,
        status: Status,
        status_uuid: str,
        *,
        name: str | None = None,
        current: float | None = None,
        initial: float | None = None,
        target: float | None = None,
        unit: str | None = None,
        precision: int | None = None,
        fraction: float | None = None,
        time_elapsed: float | None = None,
        time_remaining: float | None = None,
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
        # Ensure completed statues are not re-added and published
        if status_uuid not in self._completed_statuses:
            self._status_snapshot[status_uuid] = view
            self._publish_status_snapshot()

    def _publish_status_snapshot(self) -> None:
        if self._current is None:
            raise ValueError("Got a status update without an active task!")
        else:
            self._progress_events.publish(
                ProgressEvent(
                    task_id=self._current.task_id,
                    statuses=self._status_snapshot,
                ),
                self._current.task_id,
            )


@dataclass
class KillSignal:
    """
    Object put in the worker's task queue to tell it to shut down.
    """

    ...


def run_worker_in_own_thread(
    worker: TaskWorker, executor: ThreadPoolExecutor | None = None
) -> Future:
    """
    Helper function, make a worker run in a new thread managed by a ThreadPoolExecutor

    Args:
        worker (TaskWorker): The worker to run
        executor (Optional[ThreadPoolExecutor], optional): The executor to manage the
                                                           thread, defaults to None in
                                                           which case a new one is
                                                           created

    Returns:
        Future: Future representing worker stopping
    """

    if executor is None:
        executor = ThreadPoolExecutor(1, "run-engine-worker")
    return executor.submit(_run_worker_thread, worker)


@handle_all_exceptions
def _run_worker_thread(worker: TaskWorker) -> None:
    """
    Helper function, run a worker forever, includes support for
    printing exceptions to stdout from a non-main thread.

    Args:
        worker (TaskWorker): The worker to run
    """

    LOGGER.info("Setting up event loop")
    configure_bluesky_event_loop()
    LOGGER.info("Worker starting")
    worker.run()

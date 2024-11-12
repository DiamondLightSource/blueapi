import time
from concurrent.futures import Future

from bluesky_stomp.messaging import MessageContext, StompClient
from bluesky_stomp.models import Broker
from observability_utils.tracing import (
    get_tracer,
    start_as_current_span,
)

from blueapi.config import ApplicationConfig
from blueapi.core.bluesky_types import DataEvent
from blueapi.service.authentication import SessionManager
from blueapi.service.model import (
    DeviceModel,
    DeviceResponse,
    EnvironmentResponse,
    PlanModel,
    PlanResponse,
    TaskResponse,
    TasksListResponse,
    WorkerTask,
)
from blueapi.worker import Task, TrackableTask, WorkerEvent, WorkerState
from blueapi.worker.event import ProgressEvent, TaskStatus

from .event_bus import AnyEvent, BlueskyStreamingError, EventBusClient, OnAnyEvent
from .rest import BlueapiRestClient, BlueskyRemoteControlError

TRACER = get_tracer("client")


class BlueapiClient:
    """Unified client for controlling blueapi"""

    _rest: BlueapiRestClient
    _events: EventBusClient | None

    def __init__(
        self,
        rest: BlueapiRestClient,
        events: EventBusClient | None = None,
    ):
        self._rest = rest
        self._events = events

    @classmethod
    def from_config(cls, config: ApplicationConfig) -> "BlueapiClient":
        rest: BlueapiRestClient = BlueapiRestClient(
            config.api,
            SessionManager(config.oidc) if config.oidc else None,
        )
        if config.stomp is not None:
            stomp_client = StompClient.for_broker(
                broker=Broker(
                    host=config.stomp.host,
                    port=config.stomp.port,
                    auth=config.stomp.auth,
                )
            )
            events = EventBusClient(stomp_client)
        else:
            events = None
        return cls(rest, events)

    @start_as_current_span(TRACER)
    def get_plans(self) -> PlanResponse:
        """
        List plans available

        Returns:
            PlanResponse: Plans that can be run
        """
        return self._rest.get_plans()

    @start_as_current_span(TRACER, "name")
    def get_plan(self, name: str) -> PlanModel:
        """
        Get details of a single plan

        Args:
            name: Plan name

        Returns:
            PlanModel: Details of the plan if found
        """
        return self._rest.get_plan(name)

    @start_as_current_span(TRACER)
    def get_devices(self) -> DeviceResponse:
        """
        List devices available

        Returns:
            DeviceResponse: Devices that can be used in plans
        """

        return self._rest.get_devices()

    @start_as_current_span(TRACER, "name")
    def get_device(self, name: str) -> DeviceModel:
        """
        Get details of a single device

        Args:
            name: Device name

        Returns:
            DeviceModel: Details of the device if found
        """

        return self._rest.get_device(name)

    @start_as_current_span(TRACER)
    def get_state(self) -> WorkerState:
        """
        Get current state of the blueapi worker

        Returns:
            WorkerState: Current state
        """

        return self._rest.get_state()

    @start_as_current_span(TRACER, "defer")
    def pause(self, defer: bool = False) -> WorkerState:
        """
        Pause execution of the current task, if any

        Args:
            defer: Wait until the next checkpoint to pause.
            Defaults to False.

        Returns:
            WorkerState: Final state of the worker following
            pause operation
        """

        return self._rest.set_state(WorkerState.PAUSED, defer=defer)

    @start_as_current_span(TRACER)
    def resume(self) -> WorkerState:
        """
        Resume plan execution if previously paused

        Returns:
            WorkerState: Final state of the worker following
            resume operation
        """

        return self._rest.set_state(WorkerState.RUNNING, defer=False)

    @start_as_current_span(TRACER, "task_id")
    def get_task(self, task_id: str) -> TrackableTask[Task]:
        """
        Get a task stored by the worker

        Args:
            task_id: Unique ID for the task

        Returns:
            TrackableTask[Task]: Task details
        """
        assert task_id, "Task ID not provided!"
        return self._rest.get_task(task_id)

    @start_as_current_span(TRACER)
    def get_all_tasks(self) -> TasksListResponse:
        """
        Get a list of all task stored by the worker

        Returns:
            TasksListResponse: List of all Trackable Task
        """

        return self._rest.get_all_tasks()

    @start_as_current_span(TRACER)
    def get_active_task(self) -> WorkerTask:
        """
        Get the currently active task, if any

        Returns:
            WorkerTask: The currently active task, the task the worker
            is executing right now.
        """

        return self._rest.get_active_task()

    @start_as_current_span(TRACER, "task", "timeout")
    def run_task(
        self,
        task: Task,
        on_event: OnAnyEvent | None = None,
        timeout: float | None = None,
    ) -> WorkerEvent:
        """
        Synchronously run a task, requires a message bus connection

        Args:
            task: Task to run
            on_event: Callback for each event. Defaults to None.
            timeout: Time to wait until the task is finished.
            Defaults to None, so waits forever.

        Returns:
            WorkerEvent: The final event, which includes final details
            of task execution.
        """

        if self._events is None:
            raise RuntimeError(
                "Cannot run plans without Stomp configuration to track progress"
            )

        task_response = self.create_task(task)
        task_id = task_response.task_id

        complete: Future[WorkerEvent] = Future()

        def inner_on_event(event: AnyEvent, ctx: MessageContext) -> None:
            match event:
                case WorkerEvent(task_status=TaskStatus(task_id=test_id)):
                    relates_to_task = test_id == task_id
                case ProgressEvent(task_id=test_id):
                    relates_to_task = test_id == task_id
                case DataEvent():
                    relates_to_task = True
                case _:
                    relates_to_task = False
            if relates_to_task:
                if on_event is not None:
                    on_event(event)
                if isinstance(event, WorkerEvent) and (
                    (event.is_complete()) and (ctx.correlation_id == task_id)
                ):
                    if event.task_status is not None and event.task_status.task_failed:
                        complete.set_exception(
                            BlueskyStreamingError(
                                "\n".join(event.errors)
                                if len(event.errors) > 0
                                else "Unknown error"
                            )
                        )
                    else:
                        complete.set_result(event)

        with self._events:
            self._events.subscribe_to_all_events(inner_on_event)
            self.start_task(WorkerTask(task_id=task_id))
            return complete.result(timeout=timeout)

    @start_as_current_span(TRACER, "task")
    def create_and_start_task(self, task: Task) -> TaskResponse:
        """
        Create a new task and instruct the worker to start it
        immediately.

        Args:
            task: The task to create on the worker

        Returns:
            TaskResponse: Acknowledgement of request
        """

        response = self.create_task(task)
        worker_response = self.start_task(WorkerTask(task_id=response.task_id))
        if worker_response.task_id == response.task_id:
            return response
        else:
            raise BlueskyRemoteControlError(
                f"Tried to create and start task {response.task_id} "
                f"but {worker_response.task_id} was started instead"
            )

    @start_as_current_span(TRACER, "task")
    def create_task(self, task: Task) -> TaskResponse:
        """
        Create a new task, does not start execution

        Args:
            task: The task to create on the worker

        Returns:
            TaskResponse: Acknowledgement of request
        """

        return self._rest.create_task(task)

    @start_as_current_span(TRACER)
    def clear_task(self, task_id: str) -> TaskResponse:
        """
        Delete a stored task on the worker

        Args:
            task_id: ID for the task

        Returns:
            TaskResponse: Acknowledgement of request
        """

        return self._rest.clear_task(task_id)

    @start_as_current_span(TRACER, "task")
    def start_task(self, task: WorkerTask) -> WorkerTask:
        """
        Instruct the worker to start a stored task immediately

        Args:
            task_id: ID for the task

        Returns:
            WorkerTask: Acknowledgement of request
        """

        return self._rest.update_worker_task(task)

    @start_as_current_span(TRACER, "reason")
    def abort(self, reason: str | None = None) -> WorkerState:
        """
        Abort the plan currently being executed, if any.
        Stop execution, perform cleanup steps, mark the plan
        as failed.

        Args:
            reason: Reason for abort to include in the documents.
            Defaults to None.

        Returns:
            WorkerState: Final state of the worker following the
            abort operation.
        """

        return self._rest.cancel_current_task(
            WorkerState.ABORTING,
            reason=reason,
        )

    @start_as_current_span(TRACER)
    def stop(self) -> WorkerState:
        """
        Stop execution of the current plan early.
        Stop execution, perform cleanup steps, but still mark the plan
        as successful.

        Returns:
            WorkerState: Final state of the worker following the
            stop operation.
        """

        return self._rest.cancel_current_task(WorkerState.STOPPING)

    @start_as_current_span(TRACER)
    def get_environment(self) -> EnvironmentResponse:
        """
        Get details of the worker environment

        Returns:
            EnvironmentResponse: Details of the worker
            environment.
        """

        return self._rest.get_environment()

    @start_as_current_span(TRACER, "timeout", "polling_interval")
    def reload_environment(
        self,
        timeout: float | None = None,
        polling_interval: float = 0.5,
    ) -> EnvironmentResponse:
        """
        Teardown the worker environment and create a new one

        Args:
            timeout: Time to wait for teardown. Defaults to None,
            so waits forever.
            polling_interval: If there is a timeout, the number of
            seconds to wait between checking whether the environment
            has been successfully reloaded. Defaults to 0.5.

        Returns:
            EnvironmentResponse: Details of the new worker
            environment.
        """

        try:
            status = self._rest.delete_environment()
        except Exception as e:
            raise BlueskyRemoteControlError(
                "Failed to tear down the environment"
            ) from e
        return self._wait_for_reload(
            status,
            timeout,
            polling_interval,
        )

    @start_as_current_span(TRACER, "timeout", "polling_interval")
    def _wait_for_reload(
        self,
        status: EnvironmentResponse,
        timeout: float | None,
        polling_interval: float = 0.5,
    ) -> EnvironmentResponse:
        teardown_complete_time = time.time()
        too_late = teardown_complete_time + timeout if timeout is not None else None

        # Wait forever if there was no timeout
        while too_late is None or time.time() < too_late:
            # Poll until the environment is restarted or the timeout is reached
            status = self._rest.get_environment()
            if status.error_message is not None:
                raise BlueskyRemoteControlError(
                    f"Error reloading environment: {status.error_message}"
                )
            elif status.initialized:
                return status
            time.sleep(polling_interval)
        # If the function did not raise or return early, it timed out
        raise TimeoutError(
            f"Failed to reload the environment within {timeout} "
            "seconds, a server restart is recommended"
        )

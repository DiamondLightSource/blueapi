import logging
import time
from concurrent.futures import Future
from functools import cached_property
from pathlib import Path
from typing import Self

from bluesky_stomp.messaging import MessageContext, StompClient
from bluesky_stomp.models import Broker
from observability_utils.tracing import (
    get_tracer,
    start_as_current_span,
)

from blueapi.config import (
    ApplicationConfig,
    ConfigLoader,
    MissingStompConfigurationError,
)
from blueapi.core.bluesky_types import DataEvent
from blueapi.service.authentication import SessionManager
from blueapi.service.model import (
    DeviceModel,
    EnvironmentResponse,
    OIDCConfig,
    PlanModel,
    PythonEnvironmentResponse,
    SourceInfo,
    TaskRequest,
    TaskResponse,
    WorkerTask,
)
from blueapi.worker import WorkerEvent, WorkerState
from blueapi.worker.event import ProgressEvent, TaskStatus

from .event_bus import AnyEvent, BlueskyStreamingError, EventBusClient, OnAnyEvent
from .rest import BlueapiRestClient, BlueskyRemoteControlError

TRACER = get_tracer("client")


log = logging.getLogger(__name__)


class MissingInstrumentSessionError(Exception):
    pass


class PlanCache:
    def __init__(self, client: "BlueapiClient", plans: list[PlanModel]):
        self._cache = {
            model.name: Plan(name=model.name, model=model, client=client)
            for model in plans
        }
        for name, plan in self._cache.items():
            if name.startswith("_"):
                continue
            setattr(self, name, plan)

    def __getattr__(self, name: str) -> "Plan":
        raise AttributeError(f"No plan named '{name}' available")

    def __iter__(self):
        return iter(self._cache.values())


class DeviceCache:
    def __init__(self, rest: BlueapiRestClient):
        self._rest = rest
        self._cache = {
            model.name: DeviceRef(name=model.name, cache=self, model=model)
            for model in rest.get_devices().devices
        }
        for name, device in self._cache.items():
            if name.startswith("_"):
                continue
            setattr(self, name, device)

    def __getitem__(self, name: str) -> "DeviceRef":
        if dev := self._cache.get(name):
            return dev
        try:
            model = self._rest.get_device(name)
            device = DeviceRef(name=name, cache=self, model=model)
            self._cache[name] = device
            setattr(self, model.name, device)
            return device
        except KeyError:
            pass
        raise AttributeError(f"No device name '{name}' available")

    def __getattr__(self, name: str) -> "DeviceRef":
        if name.startswith("_"):
            return super().__getattribute__(name)
        return self[name]

    def __iter__(self):
        return iter(self._cache.values())


class DeviceRef(str):
    model: DeviceModel
    _cache: DeviceCache

    def __new__(cls, name: str, cache: DeviceCache, model: DeviceModel):
        instance = super().__new__(cls, name)
        instance.model = model
        instance._cache = cache
        return instance

    def __getattr__(self, name) -> "DeviceRef":
        if name.startswith("_"):
            raise AttributeError(f"No child device named {name}")
        return self._cache[f"{self}.{name}"]

    def __repr__(self):
        return f"Device({self})"


class Plan:
    def __init__(self, name, model: PlanModel, client: "BlueapiClient"):
        self.name = name
        self.model = model
        self._client = client
        self.__doc__ = model.description

    def __call__(self, *args, **kwargs):
        req = TaskRequest(
            name=self.name,
            params=self._build_args(*args, **kwargs),
            instrument_session=self._client.instrument_session,
        )
        self._client.run_task(req)

    @property
    def help_text(self) -> str:
        return self.model.description or f"Plan {self!r}"

    @property
    def properties(self) -> set[str]:
        return self.model.parameter_schema["properties"]

    @property
    def required(self) -> list[str]:
        return self.model.parameter_schema["required"]

    def _build_args(self, *args, **kwargs):
        log.info(
            "Building args for %s, using %s and %s",
            "[" + ",".join(self.properties) + "]",
            args,
            kwargs,
        )

        if len(args) > len(self.properties):
            raise TypeError(f"{self.name} got too many arguments")
        if extra := {k for k in kwargs if k not in self.properties}:
            raise TypeError(f"{self.name} got unexpected arguments: {extra}")

        params = {}
        # Initially fill parameters using positional args assuming the order
        # from the parameter_schema
        for req, arg in zip(self.properties, args, strict=False):
            params[req] = arg

        # Then append any values given via kwargs
        for key, value in kwargs.items():
            # If we've already assumed a positional arg was this value, bail out
            if key in params:
                raise TypeError(f"{self.name} got multiple values for {key}")
            params[key] = value

        if missing := {k for k in self.required if k not in params}:
            raise TypeError(f"Missing argument(s) for {missing}")
        return params

    def __repr__(self):
        return f"{self.name}({', '.join(self.properties)})"


class BlueapiClient:
    """Unified client for controlling blueapi"""

    _rest: BlueapiRestClient
    _events: EventBusClient | None
    _instrument_session: str | None = None

    def __init__(
        self,
        rest: BlueapiRestClient,
        events: EventBusClient | None = None,
    ):
        self._rest = rest
        self._events = events

    @cached_property
    @start_as_current_span(TRACER)
    def plans(self) -> PlanCache:
        return PlanCache(self, self._rest.get_plans().plans)

    @cached_property
    @start_as_current_span(TRACER)
    def devices(self) -> DeviceCache:
        return DeviceCache(self._rest)

    @classmethod
    def from_config_file(cls, config_file: str) -> Self:
        conf = ConfigLoader(ApplicationConfig)
        conf.use_values_from_yaml(Path(config_file))
        return cls.from_config(conf.load())

    @classmethod
    def from_config(
        cls,
        config: ApplicationConfig,
    ) -> Self:
        session_manager: SessionManager | None = None
        try:
            session_manager = SessionManager.from_cache(config.auth_token_path)
        except Exception:
            ...  # Swallow exceptions
        rest = BlueapiRestClient(config.api, session_manager=session_manager)
        if config.stomp.enabled:
            assert config.stomp.url.host is not None, "Stomp URL missing host"
            assert config.stomp.url.port is not None, "Stomp URL missing port"
            client = StompClient.for_broker(
                broker=Broker(
                    host=config.stomp.url.host,
                    port=config.stomp.url.port,
                    auth=config.stomp.auth,
                )
            )
            events = EventBusClient(client)
            return cls(rest, events)
        else:
            return cls(rest)

    @property
    def instrument_session(self) -> str:
        if self._instrument_session is None:
            raise MissingInstrumentSessionError()
        return self._instrument_session

    @instrument_session.setter
    def instrument_session(self, session: str):
        log.debug("Setting instrument_session to %s", session)
        self._instrument_session = session

    @property
    @start_as_current_span(TRACER)
    def state(self) -> WorkerState:
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

    @property
    @start_as_current_span(TRACER)
    def active_task(self) -> WorkerTask:
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
        task: TaskRequest,
        on_event: OnAnyEvent | None = None,
        timeout: float | None = None,
    ) -> WorkerEvent:
        """
        Synchronously run a task, requires a message bus connection

        Args:
            task: Request for task to run
            on_event: Callback for each event. Defaults to None.
            timeout: Time to wait until the task is finished.
            Defaults to None, so waits forever.

        Returns:
            WorkerEvent: The final event, which includes final details
            of task execution.
        """

        if self._events is None:
            raise MissingStompConfigurationError(
                "Stomp configuration required to run plans is missing or disabled"
            )

        task_response = self._rest.create_task(task)
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
            self._rest.update_worker_task(WorkerTask(task_id=task_id))
            return complete.result(timeout=timeout)

    @start_as_current_span(TRACER, "task")
    def create_and_start_task(self, task: TaskRequest) -> TaskResponse:
        """
        Create a new task and instruct the worker to start it
        immediately.

        Args:
            task: Request object for task to create on the worker

        Returns:
            TaskResponse: Acknowledgement of request
        """

        response = self._rest.create_task(task)
        worker_response = self._rest.update_worker_task(
            WorkerTask(task_id=response.task_id)
        )
        if worker_response.task_id == response.task_id:
            return response
        else:
            raise BlueskyRemoteControlError(
                f"Tried to create and start task {response.task_id} "
                f"but {worker_response.task_id} was started instead"
            )

    # @start_as_current_span(TRACER, "task")
    # def create_task(self, task: TaskRequest) -> TaskResponse:
    #     """
    #     Create a new task, does not start execution

    #     Args:
    #         task: Request object for task to create on the worker

    #     Returns:
    #         TaskResponse: Acknowledgement of request
    #     """

    #     return self._rest.create_task(task)

    # @start_as_current_span(TRACER)
    # def clear_task(self, task_id: str) -> TaskResponse:
    #     """
    #     Delete a stored task on the worker

    #     Args:
    #         task_id: ID for the task

    #     Returns:
    #         TaskResponse: Acknowledgement of request
    #     """

    #     return self._rest.clear_task(task_id)

    # @start_as_current_span(TRACER, "task")
    # def start_task(self, task: WorkerTask) -> WorkerTask:
    #     """
    #     Instruct the worker to start a stored task immediately

    #     Args:
    #         task: WorkerTask to start

    #     Returns:
    #         WorkerTask: Acknowledgement of request
    #     """

    #     return self._rest.update_worker_task(task)

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

    @property
    @start_as_current_span(TRACER)
    def environment(self) -> EnvironmentResponse:
        """Details of the worker environment"""

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

        previous_environment_id = status.environment_id
        # Wait forever if there was no timeout
        while too_late is None or time.time() < too_late:
            # Poll until the environment is restarted or the timeout is reached
            status = self._rest.get_environment()
            if status.error_message is not None:
                raise BlueskyRemoteControlError(
                    f"Error reloading environment: {status.error_message}"
                )
            elif (
                status.initialized and status.environment_id != previous_environment_id
            ):
                return status
            time.sleep(polling_interval)
        # If the function did not raise or return early, it timed out
        raise TimeoutError(
            f"Failed to reload the environment within {timeout} "
            "seconds, a server restart is recommended"
        )

    @property
    @start_as_current_span(TRACER)
    def oidc_config(self) -> OIDCConfig | None:
        """OIDC config from the server"""

        return self._rest.get_oidc_config()

    @start_as_current_span(TRACER)
    def get_python_env(
        self, name: str | None = None, source: SourceInfo | None = None
    ) -> PythonEnvironmentResponse:
        """
        Get the Python environment. This includes all installed packages and
        the scratch packages.

        Returns:
            PythonEnvironmentResponse: Details of the python environment
        """

        return self._rest.get_python_environment(name=name, source=source)

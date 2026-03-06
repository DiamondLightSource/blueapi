import asyncio
import inspect
import logging
import signal
import uuid
from collections.abc import AsyncIterator, Callable
from importlib import import_module
from multiprocessing import Pool, set_start_method
from multiprocessing.connection import Connection, Pipe
from multiprocessing.pool import Pool as PoolClass
from typing import Any, ParamSpec, TypeVar

from observability_utils.tracing import (
    get_context_propagator,
    get_tracer,
    start_as_current_span,
)
from opentelemetry.context import attach
from opentelemetry.propagate import get_global_textmap

from blueapi.config import ApplicationConfig
from blueapi.core.bluesky_types import DataEvent
from blueapi.service import interface
from blueapi.service.interface import SubHandles, setup, teardown
from blueapi.service.model import EnvironmentResponse
from blueapi.worker.event import ProgressEvent, WorkerEvent

# The default multiprocessing start method is fork
set_start_method("spawn", force=True)

LOGGER = logging.getLogger(__name__)
TRACER = get_tracer("runner")

P = ParamSpec("P")
T = TypeVar("T")

BLANK_REPORT = "The source message was blank"


def _init_worker():
    # Replace sigint to allow subprocess to be terminated
    signal.signal(signal.SIGINT, signal.SIG_IGN)


class WorkerDispatcher:
    """
    Responsible for dispatching calls required by the REST app.
    This is generally performed in a subprocess but can be run in-process for tests
    """

    _config: ApplicationConfig
    _subprocess: PoolClass | None
    _state: EnvironmentResponse

    def __init__(
        self,
        config: ApplicationConfig | None = None,
        subprocess_factory: Callable[[], PoolClass] | None = None,
    ) -> None:
        def default_subprocess_factory():
            return Pool(initializer=_init_worker, processes=1)

        self._config = config or ApplicationConfig()
        self._subprocess = None
        self._subprocess_factory = subprocess_factory or default_subprocess_factory
        self._state = EnvironmentResponse(
            environment_id=uuid.uuid4(),
            initialized=False,
        )

    @start_as_current_span(TRACER)
    def reload(self):
        """Reload the subprocess to account for any changes in python modules"""
        self.stop()
        self.start()
        LOGGER.info("Runner reloaded")

    @start_as_current_span(TRACER)
    def start(self):
        environment_id = uuid.uuid4()
        try:
            self._subprocess = self._subprocess_factory()
            self.run(setup, self._config)
            self._state = EnvironmentResponse(
                environment_id=environment_id,
                initialized=True,
            )
        except Exception as e:
            LOGGER.exception(e)
            self._state = EnvironmentResponse(
                environment_id=environment_id,
                initialized=False,
                error_message=_safe_exception_message(e),
            )

    @start_as_current_span(TRACER)
    def stop(self):
        environment_id = self._state.environment_id
        try:
            self.run(teardown)
            if self._subprocess is not None:
                self._subprocess.close()
                self._subprocess.join()
            self._state = EnvironmentResponse(
                environment_id=environment_id,
                initialized=False,
                error_message=self._state.error_message,
            )
        except Exception as e:
            LOGGER.exception(e)
            self._state = EnvironmentResponse(
                environment_id=environment_id,
                initialized=False,
                error_message=_safe_exception_message(e),
            )

    @start_as_current_span(TRACER, "function", "args", "kwargs")
    def run(
        self,
        function: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        """Call the supplied function, passing the current Span ID, if one
        exists,from the observability context into the import_and_run_function
        caller function.

        When this is deserialized in and run by the subprocess, this will allow
        its functions to use the corresponding span as their parent span."""

        if self._subprocess is None:
            raise InvalidRunnerStateError("Subprocess runner has not been started")
        if not (hasattr(function, "__name__") and hasattr(function, "__module__")):
            raise RpcError(f"{function} is anonymous, cannot be run in subprocess")
        try:
            return_type = inspect.signature(function).return_annotation
        except TypeError:
            return_type = None

        return self._subprocess.apply(
            import_and_run_function,
            (
                function.__module__,
                function.__name__,
                return_type,
                get_context_propagator(),
                *args,
            ),
            kwargs,
        )

    def event_pipe(self):
        return EventPipe(self)

    @property
    def state(self) -> EnvironmentResponse:
        return self._state


class EventStream:
    def __init__(self, rx: Connection):
        self._rx = rx

    def __aiter__(self) -> AsyncIterator[WorkerEvent | DataEvent | ProgressEvent]:
        return self

    async def __anext__(self) -> WorkerEvent | DataEvent | ProgressEvent:
        data_available = asyncio.Event()
        asyncio.get_event_loop().add_reader(self._rx.fileno(), data_available.set)
        try:
            while not self._rx.poll():
                await data_available.wait()
                data_available.clear()
            return self._rx.recv()
        except BrokenPipeError:
            raise StopAsyncIteration() from None
        finally:
            asyncio.get_event_loop().remove_reader(self._rx.fileno())


class EventPipe:
    runner: WorkerDispatcher
    handles: list[tuple[SubHandles, Connection]]

    def __init__(self, runner: WorkerDispatcher):
        self.runner = runner
        self.handles = []

    def __enter__(self) -> EventStream:
        tx, rx = Pipe()
        hnd = self.runner.run(interface.pipe_events, tx)
        LOGGER.debug("Subscribing new event pipe: %s", hnd)
        self.handles.append((hnd, tx))
        return EventStream(rx)

    def __exit__(self, *exc):
        hnd, conn = self.handles.pop()
        LOGGER.debug("Unsubscribing event pipe: %s", hnd)
        conn.close()
        self.runner.run(interface.unpipe_events, hnd)


class InvalidRunnerStateError(Exception):
    def __init__(self, message):
        super().__init__(message)


class RpcError(Exception): ...


def import_and_run_function(
    module_name: str,
    function_name: str,
    expected_type: type[T] | None,
    carrier: dict[str, Any] | None,
    *args: Any,
    **kwargs: Any,
) -> T:
    if carrier:
        ctx = get_global_textmap().extract(carrier)
        attach(ctx)
    mod = import_module(module_name)
    func: Callable[..., T] = _validate_function(
        mod.__dict__.get(function_name, None), function_name
    )
    return func(*args, **kwargs)


def _validate_function(func: Any, function_name: str) -> Callable:
    if func is None:
        raise RpcError(f"{function_name}: No such function in subprocess API")
    elif not callable(func):
        raise RpcError(f"{function_name}: Object in subprocess is not a function")
    return func


def _safe_exception_message(e: Exception) -> str:
    return _safe_message(type(e).__name__, str(e))


def _safe_message(owner: str, message: str | None) -> str:
    return f"{owner}: {BLANK_REPORT if (not message or message.isspace()) else message}"

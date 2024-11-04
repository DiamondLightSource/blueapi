import inspect
import logging
import signal
from collections.abc import Callable
from importlib import import_module
from multiprocessing import Pool, set_start_method
from multiprocessing.pool import Pool as PoolClass
from typing import Any, ParamSpec, TypeVar

from observability_utils.tracing import (
    add_span_attributes,
    get_context_propagator,
    get_tracer,
    start_as_current_span,
)
from opentelemetry.context import attach
from opentelemetry.propagate import get_global_textmap
from pydantic import TypeAdapter

from blueapi.config import ApplicationConfig
from blueapi.service.interface import setup, teardown
from blueapi.service.model import EnvironmentResponse

# The default multiprocessing start method is fork
set_start_method("spawn", force=True)

LOGGER = logging.getLogger(__name__)
TRACER = get_tracer("runner")

P = ParamSpec("P")
T = TypeVar("T")


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
    _use_subprocess: bool
    _state: EnvironmentResponse

    def __init__(
        self,
        config: ApplicationConfig | None = None,
        use_subprocess: bool = True,
    ) -> None:
        self._config = config or ApplicationConfig()
        self._subprocess = None
        self._use_subprocess = use_subprocess
        self._state = EnvironmentResponse(
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
        add_span_attributes(
            {"_use_subprocess": self._use_subprocess, "_config": self._config}
        )
        try:
            if self._use_subprocess:
                self._subprocess = Pool(initializer=_init_worker, processes=1)
            self.run(setup, self._config)
            self._state = EnvironmentResponse(initialized=True)
        except Exception as e:
            self._state = EnvironmentResponse(
                initialized=False,
                error_message=str(e),
            )
            LOGGER.exception(e)

    @start_as_current_span(TRACER)
    def stop(self):
        try:
            self.run(teardown)
            if self._subprocess is not None:
                self._subprocess.close()
                self._subprocess.join()
            self._state = EnvironmentResponse(
                initialized=False,
                error_message=self._state.error_message,
            )
        except Exception as e:
            self._state = EnvironmentResponse(
                initialized=False,
                error_message=str(e),
            )
            LOGGER.exception(e)

    @start_as_current_span(TRACER, "function", "args", "kwargs")
    def run(
        self,
        function: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        """Calls the supplied function, which is modified to accept a dict as it's new
        first param, before being passed to the subprocess runner, or just run in place.
        """
        add_span_attributes({"use_subprocess": self._use_subprocess})
        if self._use_subprocess:
            return self._run_in_subprocess(function, *args, **kwargs)
        else:
            return function(*args, **kwargs)

    @start_as_current_span(TRACER, "function", "args", "kwargs")
    def _run_in_subprocess(
        self,
        function: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        """Call the supplied function, passing the current Span ID, if one
        exists,from the observability context inro the _rpc caller function.
        When this is deserialized in and run by the subprocess, this will allow
        its functions to use the corresponding span as their parent span."""
        if self._subprocess is None:
            raise InvalidRunnerStateError("Subprocess runner has not been started")
        if not (hasattr(function, "__name__") and hasattr(function, "__module__")):
            raise RpcError(f"{function} is anonymous, cannot be run in subprocess")
        if not callable(function):
            raise RpcError(f"{function} is not Callable, cannot be run in subprocess")
        try:
            return_type = inspect.signature(function).return_annotation
        except TypeError:
            return_type = None

        return self._subprocess.apply(
            _rpc,
            (
                function.__module__,
                function.__name__,
                return_type,
                get_context_propagator(),
                *args,
            ),
            kwargs,
        )

    @property
    def state(self) -> EnvironmentResponse:
        return self._state


class InvalidRunnerStateError(Exception):
    def __init__(self, message):
        super().__init__(message)


class RpcError(Exception): ...


def _rpc(
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
    func: Callable[P, T] = _validate_function(
        mod.__dict__.get(function_name, None), function_name
    )
    value = func(*args, **kwargs)
    return _valid_return(value, expected_type)


def _valid_return(value: Any, expected_type: type[T] | None = None) -> T:
    if expected_type is None:
        return value
    else:
        return TypeAdapter(expected_type).validate_python(value)


def _validate_function(func: Any, function_name: str) -> Callable:
    if func is None:
        raise RpcError(f"{function_name}: No such function in subprocess API")
    elif not callable(func):
        raise RpcError(f"{function_name}: Object in subprocess is not a function")
    return func

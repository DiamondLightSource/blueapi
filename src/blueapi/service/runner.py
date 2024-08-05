import logging
import signal
from collections.abc import Callable
from importlib import import_module
from multiprocessing import Pool, set_start_method
from multiprocessing.pool import Pool as PoolClass
from typing import Any, TypeVar

from opentelemetry.propagate import get_global_textmap
from typing_extensions import ParamSpec

from blueapi.config import ApplicationConfig
from blueapi.service.interface import (
    setup,
    teardown,
    use_propagated_context,
)
from blueapi.service.model import EnvironmentResponse

# The default multiprocessing start method is fork
set_start_method("spawn", force=True)

LOGGER = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def get_context_propagator() -> dict[str, Any]:
    carr = {}
    get_global_textmap().inject(carr)
    return carr


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

    def reload(self):
        """Reload the subprocess to account for any changes in python modules"""
        self.stop()
        self.start()
        LOGGER.info("Runner reloaded")

    def start(self):
        try:
            if self._use_subprocess:
                self._subprocess = Pool(initializer=_init_worker, processes=1)
            self.run(setup, [self._config])
            self._state = EnvironmentResponse(initialized=True)
        except Exception as e:
            self._state = EnvironmentResponse(
                initialized=False,
                error_message=str(e),
            )
            LOGGER.exception(e)

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

    def run(
        self,
        function: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        if self._use_subprocess:
            return self._run_in_subprocess(function, *args, **kwargs)
        else:
            return function(*args, **kwargs)

    def _run_in_subprocess(
        self,
        function: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        if self._subprocess is None:
            raise InvalidRunnerStateError("Subprocess runner has not been started")
        return self._subprocess.apply(
            _rpc,
            (function.__module__, function.__name__, get_context_propagator(), *args),
            kwargs,
        )

    @property
    def state(self) -> EnvironmentResponse:
        return self._state


class InvalidRunnerStateError(Exception):
    def __init__(self, message):
        super().__init__(message)


class RpcErrpr(Exception):
    def __init__(self, message):
        super().__init__(message)


def _rpc(module_name: str, function_name: str, args, kwargs) -> T:
    mod = import_module(module_name)
    function = mod.__dict__.get(function_name)
    _validate_function(function_name, function)
    return use_propagated_context(function)(*args, **kwargs)


def _validate_function(name: str, function: Any) -> None:
    if function is None:
        raise RpcErrpr(f"{name}: No such function in subprocess API")
    elif not callable(function):
        raise RpcErrpr(f"{name}: {function}: Object in subprocess is not a function")

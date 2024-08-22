import inspect
import logging
import signal
from collections.abc import Callable, Collection, Mapping, Sequence
from importlib import import_module
from multiprocessing import Pool, set_start_method
from multiprocessing.pool import Pool as PoolClass
from typing import Any, ParamSpec, TypeVar, Union, get_args, get_origin

from blueapi.config import ApplicationConfig
from blueapi.service.interface import setup, teardown
from blueapi.service.model import EnvironmentResponse

# The default multiprocessing start method is fork
set_start_method("spawn", force=True)

LOGGER = logging.getLogger(__name__)

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

    def reload(self):
        """Reload the subprocess to account for any changes in python modules"""
        self.stop()
        self.start()
        LOGGER.info("Runner reloaded")

    def start(self):
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

    def run(self, function: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
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
    *args: Any,
    **kwargs: Any,
) -> T:
    mod = import_module(module_name)
    func: Callable[P, T] = _validate_function(
        mod.__dict__.get(function_name, None), function_name
    )
    value = func(*args, **kwargs)
    if expected_type is None or is_valid_return(value, expected_type):
        return value
    else:
        raise TypeError(
            f"{function_name} returned value of type {type(value)}"
            + f" which is incompatible with expected {expected_type}"
        )


def is_valid_return(value: Any, expected_type: type[T]) -> bool:
    if expected_type is Any:
        return True
    if expected_type is type(None):
        return value is None
    origin = get_origin(expected_type)
    if origin is None or origin is Union:  # works for Python >= 3.10
        return isinstance(value, expected_type)
    args = get_args(expected_type)
    if issubclass(origin, Mapping):
        return isinstance(value, Mapping) and all(
            is_valid_return(k, args[0]) and is_valid_return(v, args[1])
            for k, v in value.items()
        )
    if origin is tuple:  # handle ellipses specially
        assert isinstance(value, tuple)
        if args[1] is Ellipsis:
            args = (args[0],) * len(value)
        else:
            return all(
                is_valid_return(inner, arg)
                for inner, arg in zip(value, args, strict=True)
            )
    if issubclass(origin, Collection):  # list, set, etc.
        return isinstance(value, Collection) and all(
            is_valid_return(inner, args[0]) for inner in value
        )
    raise TypeError(f"Unknown origin for generic type {expected_type}")


def _validate_function(func: Any, function_name: str) -> Callable:
    if func is None:
        raise RpcError(f"{function_name}: No such function in subprocess API")
    elif not callable(func):
        raise RpcError(f"{function_name}: Object in subprocess is not a function")
    return func

import logging
import signal
from collections.abc import Callable, Iterable
from multiprocessing import Pool, set_start_method
from multiprocessing.pool import Pool as PoolClass
from typing import Any

from blueapi.config import ApplicationConfig
from blueapi.service.interface import start_worker, stop_worker
from blueapi.service.model import (
    EnvironmentResponse,
)

# The default multiprocessing start method is fork
set_start_method("spawn", force=True)

LOGGER = logging.getLogger(__name__)


def _init_worker():
    # Replace sigint to allow subprocess to be terminated
    signal.signal(signal.SIGINT, signal.SIG_IGN)


class Runner:
    """
    Responsible for dispatching calls required by the REST app.
    This is generally performed in a subprocess but can be run in-process for tests
    """

    _config: ApplicationConfig
    _subprocess: PoolClass | None
    _initialized: bool = False
    _error_message: str | None = None
    _use_subprocess: bool

    def __init__(
        self, config: ApplicationConfig | None = None, use_subprocess: bool = True
    ) -> None:
        self._config = config or ApplicationConfig()
        self._subprocess = None
        self._use_subprocess = use_subprocess

    def start(self):
        if self._subprocess is None and self._use_subprocess:
            self._subprocess = Pool(initializer=_init_worker, processes=1)
            self._subprocess.apply(
                logging.basicConfig, kwds={"level": self._config.logging.level}
            )
            try:
                self._subprocess.apply(start_worker, [self._config])
            except Exception as e:
                self._error_message = f"Error configuring blueapi: {e}"
                LOGGER.exception(self._error_message)
                return
            self._initialized = True
        if not self._use_subprocess:
            try:
                start_worker(self._config)
            except Exception as e:
                self._error_message = f"Error configuring blueapi: {e}"
                LOGGER.exception(self._error_message)
                return
            self._initialized = True

    def stop(self):
        if self._subprocess is not None:
            self._initialized = False
            self._subprocess.apply(stop_worker)
            self._subprocess.close()
            self._subprocess.join()
            self._error_message = None
            self._subprocess = None
        if (not self._use_subprocess) and (self._initialized or self._error_message):
            self._initialized = False
            stop_worker()
            self._error_message = None

    def reload_context(self):
        """Reload the subprocess to account for any changes in python modules"""
        self.stop()
        self.start()
        LOGGER.info("Context reloaded")

    def run(self, function: Callable, arguments: Iterable | None = None) -> Any:
        if self._use_subprocess:
            return self._run_in_subprocess(function, arguments)
        else:
            if arguments is None:
                arguments = []
            return function(*arguments)

    def _run_in_subprocess(
        self, function: Callable, arguments: Iterable | None = None
    ) -> Any:
        if arguments is None:
            arguments = []
        if self._subprocess is None:
            raise HandlerNotStartedError("Subprocess handler has not been started")
        return self._subprocess.apply(function, arguments)

    @property
    def state(self) -> EnvironmentResponse:
        return EnvironmentResponse(
            initialized=self._initialized,
            error_message=self._error_message,
        )


class HandlerNotStartedError(Exception):
    def __init__(self, message):
        super().__init__(message)

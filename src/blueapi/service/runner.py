import logging
import signal
from collections.abc import Callable, Iterable
from multiprocessing import Pool, set_start_method
from multiprocessing.pool import Pool as PoolClass
from typing import Any

from blueapi.config import ApplicationConfig
from blueapi.service.interface import (
    setup,
    teardown,
)
from blueapi.service.model import EnvironmentResponse

# The default multiprocessing start method is fork
set_start_method("spawn", force=True)

LOGGER = logging.getLogger(__name__)


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

    def run(self, function: Callable, arguments: Iterable | None = None) -> Any:
        arguments = arguments or []
        if self._use_subprocess:
            return self._run_in_subprocess(function, arguments)
        else:
            return function(*arguments)

    def _run_in_subprocess(
        self,
        function: Callable,
        arguments: Iterable,
    ) -> Any:
        if self._subprocess is None:
            raise InvalidRunnerStateError("Subprocess runner has not been started")
        return self._subprocess.apply(function, arguments)

    @property
    def state(self) -> EnvironmentResponse:
        return self._state


class InvalidRunnerStateError(Exception):
    def __init__(self, message):
        super().__init__(message)

import logging
import signal
from collections.abc import Callable, Iterable
from multiprocessing import Pool, set_start_method
from multiprocessing.pool import Pool as PoolClass

from blueapi.config import ApplicationConfig
from blueapi.service.handler import get_handler, setup_handler, teardown_handler
from blueapi.service.handler_base import BlueskyHandler, HandlerNotStartedError
from blueapi.service.model import DeviceModel, PlanModel, WorkerTask
from blueapi.worker.event import WorkerState
from blueapi.worker.task import Task
from blueapi.worker.worker import TrackableTask

set_start_method("spawn", force=True)
LOGGER = logging.getLogger(__name__)


def _init_worker():
    # Replace sigint to allow subprocess to be terminated
    signal.signal(signal.SIGINT, signal.SIG_IGN)


class SubprocessHandler(BlueskyHandler):
    _config: ApplicationConfig
    _subprocess: PoolClass | None
    _initialized: bool = False

    def __init__(
        self,
        config: ApplicationConfig | None = None,
    ) -> None:
        self._config = config or ApplicationConfig()
        self._subprocess = None

    def start(self):
        if self._subprocess is None:
            self._subprocess = Pool(initializer=_init_worker, processes=1)
            self._subprocess.apply(
                logging.basicConfig, kwds={"level": self._config.logging.level}
            )
            self._subprocess.apply(setup_handler, [self._config])
            self._initialized = True

    def stop(self):
        if self._subprocess is not None:
            self._initialized = False
            self._subprocess.apply(teardown_handler)
            self._subprocess.close()
            self._subprocess.join()
            self._subprocess = None

    def reload_context(self):
        self.stop()
        self.start()
        LOGGER.info("Context reloaded")

    def _run_in_subprocess(self, function: Callable, arguments: Iterable | None = None):
        if arguments is None:
            arguments = []
        if self._subprocess is None:
            raise HandlerNotStartedError("Subprocess handler has not been started")
        return self._subprocess.apply(function, arguments)

    @property
    def plans(self) -> list[PlanModel]:
        return self._run_in_subprocess(plans)

    def get_plan(self, name: str) -> PlanModel:
        return self._run_in_subprocess(get_plan, [name])

    @property
    def devices(self) -> list[DeviceModel]:
        return self._run_in_subprocess(devices)

    def get_device(self, name: str) -> DeviceModel:
        return self._run_in_subprocess(get_device, [name])

    def submit_task(self, task: Task) -> str:
        return self._run_in_subprocess(submit_task, [task])

    def clear_task(self, task_id: str) -> str:
        return self._run_in_subprocess(clear_task_by_id, [task_id])

    def begin_task(self, task: WorkerTask) -> WorkerTask:
        return self._run_in_subprocess(begin_task, [task])

    @property
    def active_task(self) -> TrackableTask | None:
        return self._run_in_subprocess(active_task)

    @property
    def state(self) -> WorkerState:
        return self._run_in_subprocess(state)

    def pause_worker(self, defer: bool | None) -> None:
        return self._run_in_subprocess(pause_worker, [defer])

    def resume_worker(self) -> None:
        return self._run_in_subprocess(resume_worker)

    def cancel_active_task(self, failure: bool, reason: str | None) -> None:
        return self._run_in_subprocess(cancel_active_task, [failure, reason])

    @property
    def tasks(self) -> list[TrackableTask]:
        return self._run_in_subprocess(tasks)

    def get_task_by_id(self, task_id: str) -> TrackableTask | None:
        return self._run_in_subprocess(get_task_by_id, [task_id])

    @property
    def initialized(self) -> bool:
        return self._initialized


# Free functions (passed to subprocess) for each of the methods required by Handler


def plans() -> list[PlanModel]:
    return get_handler().plans


def get_plan(name: str):
    return get_handler().get_plan(name)


def devices() -> list[DeviceModel]:
    return get_handler().devices


def get_device(name: str) -> DeviceModel:
    return get_handler().get_device(name)


def submit_task(task: Task) -> str:
    return get_handler().submit_task(task)


def clear_task_by_id(task_id: str) -> str:
    return get_handler().clear_task(task_id)


def begin_task(task: WorkerTask) -> WorkerTask:
    return get_handler().begin_task(task)


def active_task() -> TrackableTask | None:
    return get_handler().active_task


def state() -> WorkerState:
    return get_handler().state


def pause_worker(defer: bool | None) -> None:
    return get_handler().pause_worker(defer)


def resume_worker() -> None:
    return get_handler().resume_worker()


def cancel_active_task(failure: bool, reason: str | None) -> None:
    return get_handler().cancel_active_task(failure, reason)


def tasks() -> list[TrackableTask]:
    return get_handler().tasks


def get_task_by_id(task_id: str) -> TrackableTask | None:
    return get_handler().get_task_by_id(task_id)

from multiprocessing import Pool
from typing import List, Optional

from blueapi.config import ApplicationConfig
from blueapi.service.facade import BlueskyHandler
from blueapi.service.handler import get_handler, setup_handler, teardown_handler
from blueapi.service.model import DeviceModel, PlanModel, WorkerTask
from blueapi.worker.event import WorkerState
from blueapi.worker.task import RunPlan
from blueapi.worker.worker import TrackableTask


class SubprocessHandler(BlueskyHandler):
    _config: ApplicationConfig
    _subprocess: Pool

    def __init__(
        self,
        config: Optional[ApplicationConfig] = None,
    ) -> None:
        self._config = config or ApplicationConfig()
        self._subprocess = None

    def start(self):
        if self._subprocess is not None:
            raise ValueError("Subprocess already running")
        self._subprocess = Pool(processes=1)
        self._subprocess.apply(setup_handler, [self._config])

    def stop(self):
        self._subprocess.apply(teardown_handler)
        self._subprocess.terminate()
        self._subprocess = None

    def reload_context(self):
        self.stop()
        self.start()

    @property
    def plans(self) -> List[PlanModel]:
        return self._subprocess.apply(plans)

    def get_plan(self, name: str) -> PlanModel:
        return self._subprocess.apply(get_plan, [name])

    @property
    def devices(self) -> List[DeviceModel]:
        return self._subprocess.apply(devices)

    def get_device(self, name: str) -> DeviceModel:
        return self._subprocess.apply(get_device, [name])

    def submit_task(self, task: RunPlan) -> str:
        return self._subprocess.apply(submit_task, [task])

    def delete_task(self, task_id: str) -> str:
        return self._subprocess.apply(delete_task, [task_id])

    def begin_task(self, task: WorkerTask) -> WorkerTask:
        return self._subprocess.apply(begin_task, [task])

    @property
    def active_task(self) -> Optional[TrackableTask]:
        return self._subprocess.apply(active_task)

    @property
    def state(self) -> WorkerState:
        return self._subprocess.apply(state)

    def pause_worker(self, defer: Optional[bool]) -> None:
        return self._subprocess.apply(pause_worker, [defer])

    def resume_worker(self) -> None:
        return self._subprocess.apply(resume_worker)

    def cancel_active_task(self, failure: bool, reason: Optional[str]) -> None:
        return self._subprocess.apply(cancel_active_task, [failure, reason])

    @property
    def pending_tasks(self) -> List[TrackableTask]:
        return self._subprocess.apply(pending_tasks)

    def get_pending_task(self, task_id: str) -> Optional[TrackableTask]:
        return self._subprocess.apply(get_pending_task, [task_id])


# Free functions (passed to subprocess) for each of the methods required by Handler


def plans() -> List[PlanModel]:
    return get_handler().plans


def get_plan(name: str):
    return get_handler().get_plan(name)


def devices() -> List[DeviceModel]:
    return get_handler().devices


def get_device(name: str) -> DeviceModel:
    return get_handler().get_device(name)


def submit_task(task: RunPlan) -> str:
    return get_handler().submit_task(task)


def delete_task(task_id: str) -> str:
    return get_handler().delete_task(task_id)


def begin_task(task: WorkerTask) -> WorkerTask:
    return get_handler().begin_task(task)


def active_task() -> Optional[TrackableTask]:
    return get_handler().active_task


def state() -> WorkerState:
    return get_handler().state


def pause_worker(defer: Optional[bool]) -> None:
    return get_handler().pause_worker(defer)


def resume_worker() -> None:
    return get_handler().resume_worker()


def cancel_active_task(failure: bool, reason: Optional[str]) -> None:
    return get_handler().cancel_active_task(failure, reason)


def pending_tasks() -> List[TrackableTask]:
    return get_handler().pending_tasks


def get_pending_task(task_id: str) -> Optional[TrackableTask]:
    return get_handler().get_pending_task(task_id)

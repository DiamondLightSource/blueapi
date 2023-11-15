from abc import ABC, abstractmethod
from typing import List, Optional

from blueapi.service.model import DeviceModel, PlanModel, WorkerTask
from blueapi.worker.event import WorkerState
from blueapi.worker.task import RunPlan
from blueapi.worker.worker import TrackableTask


class BlueskyHandler(ABC):
    """Interface between web application and underlying Bluesky context and worker"""

    @property
    @abstractmethod
    def plans(self) -> List[PlanModel]:
        """
        All available plans in the BlueskyContext
        """

    @abstractmethod
    def get_plan(self, name: str) -> PlanModel:
        """
        Retrieve plan by name from the BlueskyContext
        """

    @property
    @abstractmethod
    def devices(self) -> List[DeviceModel]:
        """
        All available devices in the BlueskyContext
        """

    @abstractmethod
    def get_device(self, name: str) -> DeviceModel:
        """
        Retrieve device by name from the BlueskyContext
        """

    @abstractmethod
    def submit_task(self, task: RunPlan) -> str:
        """
        Submit a task to be run on begin_task
        """

    @abstractmethod
    def clear_pending_task(self, task_id: str) -> str:
        """Remove a pending task from the worker"""

    @abstractmethod
    def begin_task(self, task: WorkerTask) -> WorkerTask:
        """Trigger a pending task. Will fail if the worker is busy"""

    @property
    @abstractmethod
    def active_task(self) -> Optional[TrackableTask]:
        """Task the worker is currently running"""

    @property
    @abstractmethod
    def state(self) -> WorkerState:
        """State of the worker"""

    @abstractmethod
    def pause_worker(self, defer: Optional[bool]) -> None:
        """Command the worker to pause"""

    @abstractmethod
    def resume_worker(self) -> None:
        """Command the worker to resume"""

    @abstractmethod
    def cancel_active_task(self, failure: bool, reason: Optional[str]) -> None:
        """Remove the currently active task from the worker if there is one
        Returns the task_id of the active task"""

    @property
    @abstractmethod
    def pending_tasks(self) -> List[TrackableTask]:
        """Return a list of all tasks pending on the worker,
        any one of which can be triggered with begin_task"""

    @abstractmethod
    def get_pending_task(self, task_id: str) -> Optional[TrackableTask]:
        """Returns a task matching the task ID supplied,
        if the worker knows of it"""

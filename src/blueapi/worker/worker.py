from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import Field

from blueapi.core import DataEvent, EventStream
from blueapi.utils import BlueapiBaseModel

from .event import ProgressEvent, WorkerEvent, WorkerState

T = TypeVar("T")


class TrackableTask(BlueapiBaseModel, Generic[T]):
    """
    A representation of a task that the worker recognizes
    """

    task_id: str
    task: T
    is_complete: bool = False
    is_pending: bool = True
    errors: list[str] = Field(default_factory=list)


class Worker(ABC, Generic[T]):
    """
    Entity that takes and runs tasks. Intended to be a central,
    atomic worker rather than a load distributor
    """

    @abstractmethod
    def get_tasks(self) -> list[TrackableTask[T]]:
        """
        Return a list of all tasks on the worker,
        any one of which can be triggered with begin_task.

        Returns:
            List[TrackableTask[T]]: List of task objects
        """

    @abstractmethod
    def get_task_by_id(self, task_id: str) -> TrackableTask[T] | None:
        """
        Returns a task matching the task ID supplied,
        if the worker knows of it.

        Args:
            task_id: The ID of the task

        Returns:
            Optional[TrackableTask[T]]: The task matching the ID,
                None if the task ID is unknown to the worker.
        """

    def get_active_task(self) -> TrackableTask[T] | None:
        """
        Returns the task the worker is currently running

        Returns:
            Optional[TrackableTask[T]]: The current task,
                None if the worker is idle.
        """

    @abstractmethod
    def clear_task(self, task_id: str) -> str:
        """
        Remove a task from the worker

        Args:
            task_id: The ID of the task to be removed
        Returns:
            task_id of the removed task
        """

    @abstractmethod
    def cancel_active_task(
        self,
        failure: bool = False,
        reason: str | None = None,
    ) -> str:
        """
        Remove the currently active task from the worker if there is one
        Returns the task_id of the active task
        """

    @abstractmethod
    def begin_task(self, task_id: str) -> None:
        """
        Trigger a pending task. Will fail if the worker is busy.

        Args:
            task_id: The ID of the task to be triggered
        Throws:
            WorkerBusyError: If the worker is already running a task.
            KeyError: If the task ID does not exist
        """

    @abstractmethod
    def submit_task(self, task: T) -> str:
        """
        Submit a task to be run on begin_task

        Args:
            task: A description of the task
        Returns:
            str: A unique ID to refer to this task
        """

    @abstractmethod
    def start(self) -> None:
        """
        Start worker in a new thread. Does not block, configures the bluesky
        event loop in the new thread.
        """

    @abstractmethod
    def run(self) -> None:
        """
        Run all tasks that are submitted to the worker. Blocks thread.
        """

    @abstractmethod
    def stop(self) -> None:
        """
        Command the worker to gracefully stop. Blocks until it has shut down.
        """

    @abstractmethod
    def pause(self, defer=False) -> None:
        """
        Command the worker to pause.
        """

    @abstractmethod
    def resume(self) -> None:
        """
        Command the worker to resume
        """

    @property
    @abstractmethod
    def state(self) -> WorkerState:
        """
        :return: state of the worker
        """

    @property
    @abstractmethod
    def worker_events(self) -> EventStream[WorkerEvent, int]:
        """
        Events representing changes/errors in worker state

        Returns:
            EventStream[WorkerEvent, int]: Subscribable stream of events
        """

    @property
    @abstractmethod
    def progress_events(self) -> EventStream[ProgressEvent, int]:
        """
        Events representing progress in running a task

        Returns:
            EventStream[ProgressEvent, int]: Subscribable stream of events
        """

    @property
    @abstractmethod
    def data_events(self) -> EventStream[DataEvent, int]:
        """
        Events representing collection of data

        Returns:
            EventStream[DataEvent, int]: Subscribable stream of events
        """

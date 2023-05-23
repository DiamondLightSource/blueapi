from abc import ABC, abstractmethod
from typing import Generic, List, TypeVar

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
    is_error: bool = False


class Worker(ABC, Generic[T]):
    """
    Entity that takes and runs tasks. Intended to be a central,
    atomic worker rather than a load distributor
    """

    @abstractmethod
    def get_pending_tasks(self) -> List[TrackableTask[T]]:
        """
        Return a list of all tasks pending on the worker,
        any one of which can be triggered with begin_task.

        Returns:
            List[TrackableTask[T]]: List of task objects
        """

    @abstractmethod
    def clear_task(self, task_id: str) -> bool:
        """
        Remove a pending task from the worker

        Args:
            task_id: The ID of the task to be removed
        Returns:
            bool: True if the task existed in the first place
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

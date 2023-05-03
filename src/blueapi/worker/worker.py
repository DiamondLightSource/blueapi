from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from blueapi.core import DataEvent, EventStream

from .event import ProgressEvent, WorkerEvent

T = TypeVar("T")


class Worker(ABC, Generic[T]):
    """
    Entity that takes and runs tasks. Intended to be a central,
    atomic worker rather than a load distributor
    """

    @abstractmethod
    def submit_task(self, __name: str, __task: T) -> None:
        """
        Submit a task to be run

        Args:
            __name (str): A unique name to identify this task
            __task (T): The task to run
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

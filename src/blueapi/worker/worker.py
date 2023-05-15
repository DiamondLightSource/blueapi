from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar

from blueapi.core import DataEvent, EventStream

from .event import ProgressEvent, WorkerEvent, WorkerState

T = TypeVar("T")


class Worker(ABC, Generic[T]):
    """
    Entity that takes and runs tasks. Intended to be a central,
    atomic worker rather than a load distributor
    """

    @abstractmethod
    def begin_transaction(self, __task: T) -> str:
        """
        Begin a new transaction, lock the worker with a pending task,
        do not allow new transactions until this one is run or cleared.

        Args:
            __task: The task to run if this transaction is committed

        Returns:
            str: An ID for the task
        """

    @abstractmethod
    def clear_transaction(self) -> str:
        """
        Clear any existing transaction. Raise an error if
        unable.

        Returns:
            str: The ID of the task cleared
        """

    @abstractmethod
    def commit_transaction(self, __task_id: str) -> None:
        """
        Commit the pending transaction and run the
        embedded task

        Args:
            __task_id: The ID of the task to run, must match
                the pending transaction
        """

    @abstractmethod
    def get_pending(self) -> Optional[T]:
        """_summary_

        Returns:
            Optional[Task]: _description_
        """

    @abstractmethod
    def submit_task(self, __task_id: str, __task: T) -> None:
        """
        Submit a task to be run

        Args:
            __name (str): name of the plan to be run
            __task (T): The task to run
            __correlation_id (str): unique identifier of the task
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

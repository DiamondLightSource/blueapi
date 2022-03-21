from abc import ABC, abstractmethod
from typing import Callable, Generic, TypeVar

from .event import WorkerEvent

T = TypeVar("T")


class Worker(ABC, Generic[T]):
    """
    Entity that takes and runs tasks. Intended to be a central,
    atomic worker rather than a load distributor
    """

    @abstractmethod
    def submit_task(self, task: T) -> None:
        """
        Submit a task to be run

        Args:
            task (T): The task to run
        """
        ...

    @abstractmethod
    def run_forever(self) -> None:
        """
        Run all tasks as-submitted. Blocks thread.
        """
        ...

    @abstractmethod
    def subscribe(self, callback: Callable[[WorkerEvent], None]) -> int:
        """Notify worker events

        Args:
            callback (Callable[[WorkerEvent], None]): What to do with events

        Returns:
            int: An identifier for the subscription
        """

        ...

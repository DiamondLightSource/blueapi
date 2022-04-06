from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from blueapi.core import EventStreamBase

from .event import WorkerEvent

T = TypeVar("T")


class Worker(ABC, Generic[T]):
    """
    Entity that takes and runs tasks. Intended to be a central,
    atomic worker rather than a load distributor
    """

    @property
    def worker_events(self) -> EventStreamBase[WorkerEvent, int]:
        ...

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

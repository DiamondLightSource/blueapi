from abc import ABC, abstractmethod
from typing import Callable, Generic, TypeVar

from .event import WorkerEvent

T = TypeVar("T")


class Worker(ABC, Generic[T]):
    @abstractmethod
    def submit_task(self, task: T) -> None:
        ...

    @abstractmethod
    def run_forever(self) -> None:
        ...

    @abstractmethod
    def subscribe(self, callback: Callable[[WorkerEvent], None]) -> int:
        ...

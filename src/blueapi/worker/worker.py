from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class Worker(ABC, Generic[T]):
    @abstractmethod
    def submit_task(self, task: T) -> None:
        ...

    @abstractmethod
    def run_forever(self) -> None:
        ...

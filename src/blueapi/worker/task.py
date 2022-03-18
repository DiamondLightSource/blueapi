from abc import ABC, abstractmethod
from dataclasses import dataclass

from bluesky import RunEngine


@dataclass
class TaskContext:
    run_engine: RunEngine


class Task(ABC):
    @abstractmethod
    def do_task(self, ctx: TaskContext) -> None:
        ...

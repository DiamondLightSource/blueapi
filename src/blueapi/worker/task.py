from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generator

from bluesky import Msg, RunEngine


@dataclass
class TaskContext:
    run_engine: RunEngine


class Task(ABC):
    @abstractmethod
    def do_task(self, ctx: TaskContext) -> None:
        ...


@dataclass
class RunPlan(Task):
    plan: Generator[Msg, None, Any]

    def do_task(self, ctx: TaskContext) -> None:
        ctx.run_engine(self.plan)

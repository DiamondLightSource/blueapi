from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Generator

from bluesky import Msg, RunEngine


@dataclass
class TaskContext:
    run_engine: RunEngine


class Task(ABC):
    @abstractmethod
    def do_task(self, ctx: TaskContext) -> None:
        ...


class TaskState(Enum):
    REQUESTED = "REQUESTED"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"


@dataclass
class TaskEvent:
    task: Task
    state: TaskState
    timestamp: datetime


@dataclass
class RunPlan(Task):
    plan: Generator[Msg, None, Any]

    def do_task(self, ctx: TaskContext) -> None:
        ctx.run_engine(self.plan)

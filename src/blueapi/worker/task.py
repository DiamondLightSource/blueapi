from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Generator

from bluesky import Msg, RunEngine


@dataclass
class TaskContext:
    """
    Context passed to running tasks
    """

    run_engine: RunEngine


class Task(ABC):
    """
    Object that can run with a TaskContext
    """

    @abstractmethod
    def do_task(self, ctx: TaskContext) -> None:
        """
        Perform the task using the context

        Args:
            ctx (TaskContext): Context for the task
        """
        ...


@dataclass
class RunPlan(Task):
    """
    Task that will run a plan
    """

    plan: Generator[Msg, None, Any]

    def do_task(self, ctx: TaskContext) -> None:
        ctx.run_engine(self.plan)

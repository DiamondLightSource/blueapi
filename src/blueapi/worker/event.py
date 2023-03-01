from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Union

from apischema import deserializer, identity, serializer
from apischema.conversions import Conversion
from bluesky.run_engine import RunEngineStateMachine
from super_state_machine.extras import PropertyMachine, ProxyString

from .task import TaskState

# The RunEngine can return any of these three types as its state
RawRunEngineState = Union[PropertyMachine, ProxyString, str]


class WorkerState(Enum):
    """
    The state of the Runner.
    """

    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSING = "PAUSING"
    PAUSED = "PAUSED"
    HALTING = "HALTING"
    STOPPING = "STOPPING"
    ABORTING = "ABORTING"
    SUSPENDING = "SUSPENDING"
    PANICKED = "PANICKED"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_bluesky_state(cls, bluesky_state: RawRunEngineState) -> "WorkerState":
        if isinstance(bluesky_state, RunEngineStateMachine.States):
            return cls.from_bluesky_state(bluesky_state.value)
        return WorkerState(str(bluesky_state).upper())


@dataclass
class StatusView:
    """
    A snapshot of a Status, optionally representing progress
    """

    display_name: str = "UNKNOWN"
    current: Optional[float] = None
    initial: Optional[float] = None
    target: Optional[float] = None
    unit: str = "units"
    precision: int = 3
    done: bool = False
    percentage: Optional[float] = None
    time_elapsed: Optional[float] = None
    time_remaining: Optional[float] = None


class WorkerEvent(ABC):
    _union: Any = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        deserializer(Conversion(identity, source=cls, target=WorkerEvent))
        WorkerEvent._union = (
            cls if WorkerEvent._union is None else Union[WorkerEvent._union, cls]
        )
        serializer(
            Conversion(
                identity, source=WorkerEvent, target=WorkerEvent._union, inherited=False
            )
        )


@dataclass
class TaskEvent(WorkerEvent):
    """
    An event representing a progress update on a Task
    """

    state: TaskState
    task_name: str
    error_message: Optional[str] = None

    def is_task_terminated(self) -> bool:
        return self.state in (TaskState.COMPLETE, TaskState.FAILED)

    def is_error(self) -> bool:
        return self.error_message is not None or self.state is TaskState.FAILED


@dataclass
class ProgressEvent(WorkerEvent):
    task_name: str
    statuses: Mapping[str, StatusView] = field(default_factory=dict)


@dataclass
class WorkerStatusEvent(WorkerEvent):
    worker_state: WorkerState
    error_message: Optional[str] = None

    def is_error(self) -> bool:
        return self.error_message is not None or (
            self.worker_state in (WorkerState.UNKNOWN, WorkerState.PANICKED)
        )

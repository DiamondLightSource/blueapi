from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Literal, Mapping, Optional, Union

from apischema import deserializer, identity, serialized, serializer
from apischema.conversions import Conversion
from bluesky.run_engine import RunEngineStateMachine
from super_state_machine.extras import PropertyMachine, ProxyString

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


class WorkerEvent:
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

    @serialized
    @property
    def type(self) -> str:
        return type(self).__name__


@dataclass
class ProgressEvent(WorkerEvent):
    task_name: str
    statuses: Mapping[str, StatusView] = field(default_factory=dict)


@dataclass
class TaskStatus:
    task_name: str
    task_complete: bool
    task_failed: bool


@dataclass
class WorkerStatusEvent(WorkerEvent):
    state: WorkerState
    task_status: Optional[TaskStatus] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def is_error(self) -> bool:
        return (self.task_status is not None and self.task_status.task_failed) or bool(
            self.errors
        )

    def is_complete(self) -> bool:
        return self.task_status is not None and self.task_status.task_complete

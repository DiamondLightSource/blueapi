from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Union

from bluesky.run_engine import RunEngineStateMachine
from super_state_machine.extras import PropertyMachine, ProxyString

from .task import TaskState

# The RunEngine can return any of these three types as its state
RawRunEngineState = Union[PropertyMachine, ProxyString, str]


class RunnerState(Enum):
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
    def from_bluesky_state(cls, bluesky_state: RawRunEngineState) -> "RunnerState":
        if isinstance(bluesky_state, RunEngineStateMachine.States):
            return cls.from_bluesky_state(bluesky_state.value)
        return RunnerState(str(bluesky_state).upper())


@dataclass
class WorkerEvent:
    """
    Event emitted by a worker when the runner state changes
    """

    state: RunnerState
    current_task_name: Optional[str]


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


@dataclass
class TaskEvent:
    """
    An event representing a progress update on a Task
    """

    name: str
    state: TaskState
    error: Optional[str] = None
    statuses: Mapping[str, StatusView] = field(default_factory=dict)

    def is_task_terminated(self) -> bool:
        return self.state in (TaskState.COMPLETE, TaskState.FAILED)

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union

from bluesky.run_engine import RunEngineStateMachine
from super_state_machine.extras import PropertyMachine, ProxyString

from blueapi.worker.task import ActiveTask

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
class TaskEvent:
    task: ActiveTask
    error: Optional[str] = None

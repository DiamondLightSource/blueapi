from enum import Enum
from typing import List, Mapping, Optional, Union

from bluesky.run_engine import RunEngineStateMachine
from pydantic import Field
from super_state_machine.extras import PropertyMachine, ProxyString

from blueapi.utils import BlueapiBaseModel

# The RunEngine can return any of these three types as its state
RawRunEngineState = Union[PropertyMachine, ProxyString, str]


class WorkerState(str, Enum):
    """
    The state of the Worker.
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
        """Convert the state of a bluesky RunEngine

        Args:
            bluesky_state: Bluesky RunEngine state

        Returns:
            RunnerState: Mapped RunEngine state
        """

        if isinstance(bluesky_state, RunEngineStateMachine.States):
            return cls.from_bluesky_state(bluesky_state.value)
        return WorkerState(str(bluesky_state).upper())


class StatusView(BlueapiBaseModel):
    """
    A snapshot of a Status of an operation, optionally representing progress
    """

    display_name: str = Field(
        description="Human-readable name indicating what this status describes",
        default="Unknown",
    )
    current: Optional[float] = Field(
        description="Current value of operation progress, if known", default=None
    )
    initial: Optional[float] = Field(
        description="Initial value of operation progress, if known", default=None
    )
    target: Optional[float] = Field(
        description="Target value operation of progress, if known", default=None
    )
    unit: str = Field(description="Units of progress", default="units")
    precision: int = Field(
        description="Sensible precision of progress to display", default=3
    )
    done: bool = Field(
        description="Whether the operation this status describes is complete",
        default=False,
    )
    percentage: Optional[float] = Field(
        description="Percentage of status completion, if known", default=None
    )
    time_elapsed: Optional[float] = Field(
        description="Time elapsed since status operation beginning, if known",
        default=None,
    )
    time_remaining: Optional[float] = Field(
        description="Estimated time remaining until operation completion, if known",
        default=None,
    )


class ProgressEvent(BlueapiBaseModel):
    """
    Event describing the progress of processes within a running task,
    such as moving motors and exposing detectors.
    """

    task_name: str
    statuses: Mapping[str, StatusView] = Field(default_factory=dict)


class TaskStatus(BlueapiBaseModel):
    """
    Status of a task the worker is running.
    """

    task_name: str
    task_complete: bool
    task_failed: bool


class WorkerEvent(BlueapiBaseModel):
    """
    Event describing the state of the worker and any tasks it's running.
    Includes error and warning information.
    """

    state: WorkerState
    task_status: Optional[TaskStatus] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    def is_error(self) -> bool:
        return (self.task_status is not None and self.task_status.task_failed) or bool(
            self.errors
        )

    def is_complete(self) -> bool:
        return self.task_status is not None and self.task_status.task_complete

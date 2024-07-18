from collections.abc import Iterable as _Iterable
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper

DESCRIPTOR: _descriptor.FileDescriptor

class TaskStatusEnum(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PENDING: _ClassVar[TaskStatusEnum]
    COMPLETE: _ClassVar[TaskStatusEnum]
    ERROR: _ClassVar[TaskStatusEnum]
    RUNNING: _ClassVar[TaskStatusEnum]

class WorkerState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    IDLE: _ClassVar[WorkerState]
    BUSY: _ClassVar[WorkerState]
    PAUSING: _ClassVar[WorkerState]
    PAUSED: _ClassVar[WorkerState]
    HALTING: _ClassVar[WorkerState]
    STOPPING: _ClassVar[WorkerState]
    ABORTING: _ClassVar[WorkerState]
    SUSPENDING: _ClassVar[WorkerState]
    PANICKED: _ClassVar[WorkerState]
    UNKNOWN: _ClassVar[WorkerState]
PENDING: TaskStatusEnum
COMPLETE: TaskStatusEnum
ERROR: TaskStatusEnum
RUNNING: TaskStatusEnum
IDLE: WorkerState
BUSY: WorkerState
PAUSING: WorkerState
PAUSED: WorkerState
HALTING: WorkerState
STOPPING: WorkerState
ABORTING: WorkerState
SUSPENDING: WorkerState
PANICKED: WorkerState
UNKNOWN: WorkerState

class WorkerStateMessage(_message.Message):
    __slots__ = ("state",)
    STATE_FIELD_NUMBER: _ClassVar[int]
    state: WorkerState
    def __init__(self, state: WorkerState | str | None = ...) -> None: ...

class StatusView(_message.Message):
    __slots__ = ("display_name", "current", "initial", "target", "unit", "precision", "done", "percentage", "time_elapsed", "time_remaining")
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    CURRENT_FIELD_NUMBER: _ClassVar[int]
    INITIAL_FIELD_NUMBER: _ClassVar[int]
    TARGET_FIELD_NUMBER: _ClassVar[int]
    UNIT_FIELD_NUMBER: _ClassVar[int]
    PRECISION_FIELD_NUMBER: _ClassVar[int]
    DONE_FIELD_NUMBER: _ClassVar[int]
    PERCENTAGE_FIELD_NUMBER: _ClassVar[int]
    TIME_ELAPSED_FIELD_NUMBER: _ClassVar[int]
    TIME_REMAINING_FIELD_NUMBER: _ClassVar[int]
    display_name: str
    current: float
    initial: float
    target: float
    unit: str
    precision: int
    done: bool
    percentage: float
    time_elapsed: float
    time_remaining: float
    def __init__(self, display_name: str | None = ..., current: float | None = ..., initial: float | None = ..., target: float | None = ..., unit: str | None = ..., precision: int | None = ..., done: bool = ..., percentage: float | None = ..., time_elapsed: float | None = ..., time_remaining: float | None = ...) -> None: ...

class ProgressEvent(_message.Message):
    __slots__ = ("task_id", "statuses")
    class StatusesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: StatusView
        def __init__(self, key: str | None = ..., value: StatusView | _Mapping | None = ...) -> None: ...
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    STATUSES_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    statuses: _containers.MessageMap[str, StatusView]
    def __init__(self, task_id: str | None = ..., statuses: _Mapping[str, StatusView] | None = ...) -> None: ...

class TaskStatus(_message.Message):
    __slots__ = ("task_id", "task_complete", "task_failed")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    TASK_COMPLETE_FIELD_NUMBER: _ClassVar[int]
    TASK_FAILED_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    task_complete: bool
    task_failed: bool
    def __init__(self, task_id: str | None = ..., task_complete: bool = ..., task_failed: bool = ...) -> None: ...

class WorkerEvent(_message.Message):
    __slots__ = ("state", "task_status", "errors", "warnings")
    STATE_FIELD_NUMBER: _ClassVar[int]
    TASK_STATUS_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    WARNINGS_FIELD_NUMBER: _ClassVar[int]
    state: WorkerStateMessage
    task_status: TaskStatus
    errors: _containers.RepeatedScalarFieldContainer[str]
    warnings: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, state: WorkerStateMessage | _Mapping | None = ..., task_status: TaskStatus | _Mapping | None = ..., errors: _Iterable[str] | None = ..., warnings: _Iterable[str] | None = ...) -> None: ...

class TrackableTask(_message.Message):
    __slots__ = ("task_id", "task", "is_complete", "is_pending", "errors")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    TASK_FIELD_NUMBER: _ClassVar[int]
    IS_COMPLETE_FIELD_NUMBER: _ClassVar[int]
    IS_PENDING_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    task: str
    is_complete: bool
    is_pending: bool
    errors: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, task_id: str | None = ..., task: str | None = ..., is_complete: bool = ..., is_pending: bool = ..., errors: _Iterable[str] | None = ...) -> None: ...

class StateChangeRequest(_message.Message):
    __slots__ = ("defer", "new_state", "reason")
    DEFER_FIELD_NUMBER: _ClassVar[int]
    NEW_STATE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    defer: bool
    new_state: WorkerState
    reason: str
    def __init__(self, defer: bool = ..., new_state: WorkerState | str | None = ..., reason: str | None = ...) -> None: ...

class Task(_message.Message):
    __slots__ = ("name", "params")
    class ParamsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: str | None = ..., value: str | None = ...) -> None: ...
    NAME_FIELD_NUMBER: _ClassVar[int]
    PARAMS_FIELD_NUMBER: _ClassVar[int]
    name: str
    params: _containers.ScalarMap[str, str]
    def __init__(self, name: str | None = ..., params: _Mapping[str, str] | None = ...) -> None: ...

class TaskResponse(_message.Message):
    __slots__ = ("task_id",)
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    def __init__(self, task_id: str | None = ...) -> None: ...

class TasksListResponse(_message.Message):
    __slots__ = ("tasks",)
    TASKS_FIELD_NUMBER: _ClassVar[int]
    tasks: _containers.RepeatedCompositeFieldContainer[TrackableTask]
    def __init__(self, tasks: _Iterable[TrackableTask | _Mapping] | None = ...) -> None: ...

class ValidationError(_message.Message):
    __slots__ = ("loc", "msg", "type")
    LOC_FIELD_NUMBER: _ClassVar[int]
    MSG_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    loc: _containers.RepeatedScalarFieldContainer[str]
    msg: str
    type: str
    def __init__(self, loc: _Iterable[str] | None = ..., msg: str | None = ..., type: str | None = ...) -> None: ...

class WorkerTask(_message.Message):
    __slots__ = ("task_id",)
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    def __init__(self, task_id: str | None = ...) -> None: ...

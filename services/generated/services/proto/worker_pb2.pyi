from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

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
    def __init__(self, state: _Optional[_Union[WorkerState, str]] = ...) -> None: ...

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
    def __init__(self, display_name: _Optional[str] = ..., current: _Optional[float] = ..., initial: _Optional[float] = ..., target: _Optional[float] = ..., unit: _Optional[str] = ..., precision: _Optional[int] = ..., done: bool = ..., percentage: _Optional[float] = ..., time_elapsed: _Optional[float] = ..., time_remaining: _Optional[float] = ...) -> None: ...

class ProgressEvent(_message.Message):
    __slots__ = ("task_id", "statuses")
    class StatusesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: StatusView
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[StatusView, _Mapping]] = ...) -> None: ...
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    STATUSES_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    statuses: _containers.MessageMap[str, StatusView]
    def __init__(self, task_id: _Optional[str] = ..., statuses: _Optional[_Mapping[str, StatusView]] = ...) -> None: ...

class TaskStatus(_message.Message):
    __slots__ = ("task_id", "task_complete", "task_failed")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    TASK_COMPLETE_FIELD_NUMBER: _ClassVar[int]
    TASK_FAILED_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    task_complete: bool
    task_failed: bool
    def __init__(self, task_id: _Optional[str] = ..., task_complete: bool = ..., task_failed: bool = ...) -> None: ...

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
    def __init__(self, state: _Optional[_Union[WorkerStateMessage, _Mapping]] = ..., task_status: _Optional[_Union[TaskStatus, _Mapping]] = ..., errors: _Optional[_Iterable[str]] = ..., warnings: _Optional[_Iterable[str]] = ...) -> None: ...

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
    def __init__(self, task_id: _Optional[str] = ..., task: _Optional[str] = ..., is_complete: bool = ..., is_pending: bool = ..., errors: _Optional[_Iterable[str]] = ...) -> None: ...

class StateChangeRequest(_message.Message):
    __slots__ = ("defer", "new_state", "reason")
    DEFER_FIELD_NUMBER: _ClassVar[int]
    NEW_STATE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    defer: bool
    new_state: WorkerState
    reason: str
    def __init__(self, defer: bool = ..., new_state: _Optional[_Union[WorkerState, str]] = ..., reason: _Optional[str] = ...) -> None: ...

class Task(_message.Message):
    __slots__ = ("name", "params")
    class ParamsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    NAME_FIELD_NUMBER: _ClassVar[int]
    PARAMS_FIELD_NUMBER: _ClassVar[int]
    name: str
    params: _containers.ScalarMap[str, str]
    def __init__(self, name: _Optional[str] = ..., params: _Optional[_Mapping[str, str]] = ...) -> None: ...

class TaskResponse(_message.Message):
    __slots__ = ("task_id",)
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    def __init__(self, task_id: _Optional[str] = ...) -> None: ...

class TasksListResponse(_message.Message):
    __slots__ = ("tasks",)
    TASKS_FIELD_NUMBER: _ClassVar[int]
    tasks: _containers.RepeatedCompositeFieldContainer[TrackableTask]
    def __init__(self, tasks: _Optional[_Iterable[_Union[TrackableTask, _Mapping]]] = ...) -> None: ...

class ValidationError(_message.Message):
    __slots__ = ("loc", "msg", "type")
    LOC_FIELD_NUMBER: _ClassVar[int]
    MSG_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    loc: _containers.RepeatedScalarFieldContainer[str]
    msg: str
    type: str
    def __init__(self, loc: _Optional[_Iterable[str]] = ..., msg: _Optional[str] = ..., type: _Optional[str] = ...) -> None: ...

class WorkerTask(_message.Message):
    __slots__ = ("task_id",)
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    def __init__(self, task_id: _Optional[str] = ...) -> None: ...

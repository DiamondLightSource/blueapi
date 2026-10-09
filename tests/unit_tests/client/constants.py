import uuid

from blueapi.service.model import (
    DeviceModel,
    DeviceResponse,
    EnvironmentResponse,
    PlanModel,
    PlanResponse,
    TasksListResponse,
    WorkerTask,
)
from blueapi.worker import Task, TrackableTask, WorkerEvent, WorkerState
from blueapi.worker.event import TaskError, TaskResult, TaskStatus

PLANS = PlanResponse(
    plans=[
        PlanModel(name="foo"),
        PlanModel(name="bar"),
    ]
)
PLAN = PlanModel(name="foo")
FULL_PLAN = PlanModel(
    name="foobar",
    description="Description of plan foobar",
    schema={
        "title": "foobar",
        "description": "Model description of plan foobar",
        "properties": {
            "one": {},
            "two": {},
        },
        "required": ["one"],
    },
)
DEVICES = DeviceResponse(
    devices=[
        DeviceModel(name="foo", protocols=[]),
        DeviceModel(name="bar", protocols=[]),
    ]
)
DEVICE = DeviceModel(name="foo", protocols=[])
TASK = TrackableTask(task_id="foo", task=Task(name="bar", params={}))
TASKS = TasksListResponse(tasks=[TASK])
ACTIVE_TASK = WorkerTask(task_id="bar")
ENVIRONMENT_ID = uuid.uuid4()
NEW_ENVIRONMENT_ID = uuid.uuid4()
ENV = EnvironmentResponse(environment_id=ENVIRONMENT_ID, initialized=True)
NEW_ENV = EnvironmentResponse(environment_id=NEW_ENVIRONMENT_ID, initialized=True)
COMPLETE_EVENT = WorkerEvent(
    state=WorkerState.IDLE,
    task_status=TaskStatus(
        task_id="foo",
        task_complete=True,
        task_failed=False,
        result=TaskResult(type="NoneType", result=None),
    ),
)
FAILED_EVENT = WorkerEvent(
    state=WorkerState.IDLE,
    task_status=TaskStatus(
        task_id="foo",
        task_complete=True,
        task_failed=True,
        result=TaskError(type="PlanFailure", message="The plan failed"),
    ),
)

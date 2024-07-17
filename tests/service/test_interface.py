import uuid
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
from ophyd.sim import SynAxis

from blueapi.config import ApplicationConfig, StompConfig
from blueapi.core import MsgGenerator
from blueapi.core.context import BlueskyContext
from blueapi.service.worker.main import (
    teardown,
    setup,
    get_active_task,
    context,
    get_plans,
    get_plan,
    get_devices,
    get_device,
    submit_task,
    clear_task,
    begin_task,
    get_tasks_by_status,
    get_worker_state,
    pause_worker,
    resume_worker,
    cancel_active_task,
    get_tasks,
    get_task_by_id,
)
from blueapi.service.worker.model import DeviceModel, PlanModel, WorkerTask
from blueapi.worker.event import TaskStatusEnum, WorkerState
from blueapi.worker.task import Task
from blueapi.worker.worker import TrackableTask
from blueapi.config import EnvironmentConfig


@pytest.fixture(autouse=True)
def ensure_worker_stopped():
    """This saves every test having to call this at the end.
    Additionally, without this the tests would hang in the case
    of an assertion error. The start_worker method is not managed by a fixture
    as some of the tests require it to be customised."""
    yield
    # if interface.get_state():
    teardown()


@pytest.mark.skip
def test_start_worker_raises_if_already_started():
    setup(ApplicationConfig())
    with pytest.raises(Exception):
        setup(ApplicationConfig())

@pytest.mark.skip
def test_teardown_raises_if_already_started():
    setup(ApplicationConfig())
    teardown()
    with pytest.raises(Exception):
        teardown()

@pytest.mark.skip
def test_exception_if_used_before_started():
    with pytest.raises(Exception):
        get_active_task()


def test_stomp_config():
    stomp_config = StompConfig()
    config = ApplicationConfig()
    config.stomp = stomp_config
    setup(config)


def my_plan() -> MsgGenerator:
    """My plan does cool stuff."""
    yield from {}


def my_second_plan(repeats: int) -> MsgGenerator:
    """Plan B."""
    yield from {}


# @patch("blueapi.service.BlueskyContext.plans", create=True)
# def test_get_plans(context_plans_mock: MagicMock):
def test_get_plans():
    setup(ApplicationConfig(env=EnvironmentConfig(sources=[])))
    context().plan(my_plan)
    context().plan(my_second_plan)

    assert get_plans() == [
        PlanModel(
            name="my_plan",
            description="My plan does cool stuff.",
            parameter_schema={
                "title": "my_plan",
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        ),
        PlanModel(
            name="my_second_plan",
            description="Plan B.",
            parameter_schema={
                "title": "my_second_plan",
                "type": "object",
                "properties": {"repeats": {"title": "Repeats", "type": "integer"}},
                "required": ["repeats"],
                "additionalProperties": False,
            },
        ),
    ]


def test_get_plan():
    context().plan(my_plan)
    context().plan(my_second_plan)
    setup(ApplicationConfig())

    assert get_plan("my_plan") == PlanModel(
        name="my_plan",
        description="My plan does cool stuff.",
        parameter_schema={
            "title": "my_plan",
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    )

    with pytest.raises(KeyError):
        get_plan("non_existing_plan")


@dataclass
class MyDevice:
    name: str


def test_get_devices():
    setup(ApplicationConfig(env=EnvironmentConfig(sources=[])))
    context().device(MyDevice(name="my_device"))
    context().device(SynAxis(name="my_axis"))

    assert get_devices() == [
        DeviceModel(name="my_device", protocols=["HasName"]),
        DeviceModel(
            name="my_axis",
            protocols=[
                "Checkable",
                "HasHints",
                "HasName",
                "HasParent",
                "Movable",
                "Pausable",
                "Readable",
                "Stageable",
                "Stoppable",
                "Subscribable",
                "Configurable",
                "Triggerable",
            ],
        ),
    ]


def test_get_device():
    context().device(MyDevice(name="my_device"))
    setup(ApplicationConfig())
    assert get_device("my_device") == DeviceModel(
        name="my_device", protocols=["HasName"]
    )

    with pytest.raises(KeyError):
        assert get_device("non_existing_device")


def test_submit_task():
    setup(ApplicationConfig(env=EnvironmentConfig(sources=[])))
    context().plan(my_plan)
    task = Task(name="my_plan")
    mock_uuid_value = "8dfbb9c2-7a15-47b6-bea8-b6b77c31d3d9"
    with patch.object(uuid, "uuid4") as uuid_mock:
        uuid_mock.return_value = uuid.UUID(mock_uuid_value)
        task_uuid = submit_task(task)
    assert task_uuid == mock_uuid_value


def test_clear_task():
    setup(ApplicationConfig(env=EnvironmentConfig(sources=[])))
    context().plan(my_plan)
    task = Task(name="my_plan")
    mock_uuid_value = "3d858a62-b40a-400f-82af-8d2603a4e59a"
    with patch.object(uuid, "uuid4") as uuid_mock:
        uuid_mock.return_value = uuid.UUID(mock_uuid_value)
        submit_task(task)

    clear_task_return = clear_task(mock_uuid_value)
    assert clear_task_return == mock_uuid_value


@patch("blueapi.service.worker.main.TaskWorker.begin_task")
def test_begin_task(worker_mock: MagicMock):
    setup(ApplicationConfig())
    uuid_value = "350043fd-597e-41a7-9a92-5d5478232cf7"
    task = WorkerTask(task_id=uuid_value)
    returned_task = begin_task(task)
    assert task == returned_task
    worker_mock.assert_called_once_with(uuid_value)


@patch("blueapi.service.worker.main.TaskWorker.begin_task")
def test_begin_task_no_task_id(worker_mock: MagicMock):
    setup(ApplicationConfig())
    task = WorkerTask()
    returned_task = begin_task(task)
    assert task == returned_task
    worker_mock.assert_not_called()


@patch("blueapi.service.worker.main.TaskWorker.get_tasks_by_status")
def test_get_tasks_by_status(get_tasks_by_status_mock: MagicMock):
    pending_task1 = TrackableTask(task_id="0", task=None)
    pending_task2 = TrackableTask(task_id="1", task=None)
    running_task = TrackableTask(task_id="2", task=None)

    def mock_tasks_by_status(status: TaskStatusEnum) -> list[TrackableTask]:
        if status == TaskStatusEnum.PENDING:
            return [pending_task1, pending_task2]
        elif status == TaskStatusEnum.RUNNING:
            return [running_task]
        else:
            return []

    get_tasks_by_status_mock.side_effect = mock_tasks_by_status

    setup(ApplicationConfig())

    assert get_tasks_by_status(TaskStatusEnum.PENDING) == [
        pending_task1,
        pending_task2,
    ]
    assert get_tasks_by_status(TaskStatusEnum.RUNNING) == [running_task]
    assert get_tasks_by_status(TaskStatusEnum.COMPLETE) == []


def test_get_active_task():
    setup(ApplicationConfig())
    assert get_active_task() is None


def test_get_worker_state():
    setup(ApplicationConfig())
    assert get_worker_state() == WorkerState.IDLE


@patch("blueapi.service.worker.main.TaskWorker.pause")
def test_pause_worker(pause_worker_mock: MagicMock):
    setup(ApplicationConfig())
    pause_worker(False)
    pause_worker_mock.assert_called_once_with(False)

    pause_worker_mock.reset_mock()
    pause_worker(True)
    pause_worker_mock.assert_called_once_with(True)


@patch("blueapi.service.worker.main.TaskWorker.resume")
def test_resume_worker(resume_worker_mock: MagicMock):
    setup(ApplicationConfig())
    resume_worker()
    resume_worker_mock.assert_called_once()


@patch("blueapi.service.worker.main.TaskWorker.cancel_active_task")
def test_cancel_active_task(cancel_active_task_mock: MagicMock):
    setup(ApplicationConfig())
    fail = True
    reason = "End of session"
    task_id = "789"
    cancel_active_task_mock.return_value = task_id
    assert cancel_active_task(fail, reason) == task_id
    cancel_active_task_mock.assert_called_once_with(fail, reason)


@patch("blueapi.service.worker.main.TaskWorker.get_tasks")
def test_get_tasks(get_tasks_mock: MagicMock):
    tasks = [
        TrackableTask(task_id="0", task=None),
        TrackableTask(task_id="1", task=None),
        TrackableTask(task_id="2", task=None),
    ]
    get_tasks_mock.return_value = tasks

    setup(ApplicationConfig())

    assert get_tasks() == tasks


def test_get_task_by_id():
    setup(ApplicationConfig(env=EnvironmentConfig(sources=[])))
    context().plan(my_plan)

    task_id = submit_task(Task(name="my_plan"))

    assert get_task_by_id(task_id) == TrackableTask(
        task_id=task_id,
        task=Task(name="my_plan", params={}),
        is_complete=False,
        is_pending=True,
        errors=[],
    )

import uuid
from dataclasses import dataclass
from unittest.mock import ANY, MagicMock, Mock, patch

import pytest
from bluesky_stomp.messaging import StompClient
from ophyd.sim import SynAxis
from stomp.connect import StompConnection11 as Connection

from blueapi.config import ApplicationConfig, StompConfig
from blueapi.core import MsgGenerator
from blueapi.core.context import BlueskyContext
from blueapi.service import interface
from blueapi.service.model import DeviceModel, PlanModel, WorkerTask
from blueapi.worker.event import TaskStatusEnum, WorkerState
from blueapi.worker.task import Task
from blueapi.worker.task_worker import TrackableTask


@pytest.fixture
def mock_connection() -> Mock:
    return Mock(spec=Connection)


@pytest.fixture
def mock_stomp_client(mock_connection: Mock) -> StompClient:
    stomp_client = StompClient(conn=mock_connection)
    stomp_client.disconnect = MagicMock()
    return stomp_client


@pytest.fixture(autouse=True)
def ensure_worker_stopped():
    """This saves every test having to call this at the end.
    Additionally, without this the tests would hang in the case
    of an assertion error. The start_worker method is not managed by a fixture
    as some of the tests require it to be customised."""
    yield
    interface.teardown()


def my_plan() -> MsgGenerator:
    """My plan does cool stuff."""
    yield from {}


def my_second_plan(repeats: int) -> MsgGenerator:
    """Plan B."""
    yield from {}


@patch("blueapi.service.interface.context")
def test_get_plans(context_mock: MagicMock):
    context = BlueskyContext()
    context.register_plan(my_plan)
    context.register_plan(my_second_plan)
    context_mock.return_value = context

    assert interface.get_plans() == [
        PlanModel(
            name="my_plan",
            description="My plan does cool stuff.",
            schema={
                "title": "my_plan",
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        ),
        PlanModel(
            name="my_second_plan",
            description="Plan B.",
            schema={
                "title": "my_second_plan",
                "type": "object",
                "properties": {"repeats": {"title": "Repeats", "type": "integer"}},
                "required": ["repeats"],
                "additionalProperties": False,
            },
        ),
    ]


@patch("blueapi.service.interface.context")
def test_get_plan(context_mock: MagicMock):
    context = BlueskyContext()
    context.register_plan(my_plan)
    context.register_plan(my_second_plan)
    context_mock.return_value = context

    assert interface.get_plan("my_plan") == PlanModel(
        name="my_plan",
        description="My plan does cool stuff.",
        schema={
            "title": "my_plan",
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    )

    with pytest.raises(KeyError):
        interface.get_plan("non_existing_plan")


@dataclass
class MyDevice:
    name: str


@patch("blueapi.service.interface.context")
def test_get_devices(context_mock: MagicMock):
    context = BlueskyContext()
    context.register_device(MyDevice(name="my_device"))
    context.register_device(SynAxis(name="my_axis"))
    context_mock.return_value = context

    assert interface.get_devices() == [
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


@patch("blueapi.service.interface.context")
def test_get_device(context_mock: MagicMock):
    context = BlueskyContext()
    context.register_device(MyDevice(name="my_device"))
    context_mock.return_value = context

    assert interface.get_device("my_device") == DeviceModel(
        name="my_device", protocols=["HasName"]
    )

    with pytest.raises(KeyError):
        assert interface.get_device("non_existing_device")


@patch("blueapi.service.interface.context")
def test_submit_task(context_mock: MagicMock):
    context = BlueskyContext()
    context.register_plan(my_plan)
    task = Task(name="my_plan")
    context_mock.return_value = context
    mock_uuid_value = "8dfbb9c2-7a15-47b6-bea8-b6b77c31d3d9"
    with patch.object(uuid, "uuid4") as uuid_mock:
        uuid_mock.return_value = uuid.UUID(mock_uuid_value)
        task_uuid = interface.submit_task(task)
    assert task_uuid == mock_uuid_value


@patch("blueapi.service.interface.context")
def test_clear_task(context_mock: MagicMock):
    context = BlueskyContext()
    context.register_plan(my_plan)
    task = Task(name="my_plan")
    context_mock.return_value = context
    mock_uuid_value = "3d858a62-b40a-400f-82af-8d2603a4e59a"
    with patch.object(uuid, "uuid4") as uuid_mock:
        uuid_mock.return_value = uuid.UUID(mock_uuid_value)
        interface.submit_task(task)

    clear_task_return = interface.clear_task(mock_uuid_value)
    assert clear_task_return == mock_uuid_value


@patch("blueapi.service.interface.TaskWorker.begin_task")
def test_begin_task(worker_mock: MagicMock):
    uuid_value = "350043fd-597e-41a7-9a92-5d5478232cf7"
    task = WorkerTask(task_id=uuid_value)
    returned_task = interface.begin_task(task)
    assert task == returned_task
    worker_mock.assert_called_once_with(uuid_value)


@patch("blueapi.service.interface.TaskWorker.begin_task")
def test_begin_task_no_task_id(worker_mock: MagicMock):
    task = WorkerTask(task_id=None)
    returned_task = interface.begin_task(task)
    assert task == returned_task
    worker_mock.assert_not_called()


@patch("blueapi.service.interface.TaskWorker.get_tasks_by_status")
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

    assert interface.get_tasks_by_status(TaskStatusEnum.PENDING) == [
        pending_task1,
        pending_task2,
    ]
    assert interface.get_tasks_by_status(TaskStatusEnum.RUNNING) == [running_task]
    assert interface.get_tasks_by_status(TaskStatusEnum.COMPLETE) == []


def test_get_active_task():
    assert interface.get_active_task() is None


def test_get_worker_state():
    assert interface.get_worker_state() == WorkerState.IDLE


@patch("blueapi.service.interface.TaskWorker.pause")
def test_pause_worker(pause_worker_mock: MagicMock):
    interface.pause_worker(False)
    pause_worker_mock.assert_called_once_with(False)

    pause_worker_mock.reset_mock()
    interface.pause_worker(True)
    pause_worker_mock.assert_called_once_with(True)


@patch("blueapi.service.interface.TaskWorker.resume")
def test_resume_worker(resume_worker_mock: MagicMock):
    interface.resume_worker()
    resume_worker_mock.assert_called_once()


@patch("blueapi.service.interface.TaskWorker.cancel_active_task")
def test_cancel_active_task(cancel_active_task_mock: MagicMock):
    fail = True
    reason = "End of session"
    task_id = "789"
    cancel_active_task_mock.return_value = task_id
    assert interface.cancel_active_task(fail, reason) == task_id
    cancel_active_task_mock.assert_called_once_with(fail, reason)


@patch("blueapi.service.interface.TaskWorker.get_tasks")
def test_get_tasks(get_tasks_mock: MagicMock):
    tasks = [
        TrackableTask(task_id="0", task=None),
        TrackableTask(task_id="1", task=None),
        TrackableTask(task_id="2", task=None),
    ]
    get_tasks_mock.return_value = tasks

    assert interface.get_tasks() == tasks


@patch("blueapi.service.interface.context")
def test_get_task_by_id(context_mock: MagicMock):
    context = BlueskyContext()
    context.register_plan(my_plan)
    context_mock.return_value = context

    task_id = interface.submit_task(Task(name="my_plan"))

    assert interface.get_task_by_id(task_id) == TrackableTask.model_construct(
        task_id=task_id,
        request_id=ANY,
        task=Task(name="my_plan", params={}),
        is_complete=False,
        is_pending=True,
        errors=[],
    )


def test_stomp_config(mock_stomp_client: StompClient):
    with patch(
        "blueapi.service.interface.StompClient.for_broker",
        return_value=mock_stomp_client,
    ):
        interface.set_config(ApplicationConfig(stomp=StompConfig()))
        assert interface.stomp_client() is not None

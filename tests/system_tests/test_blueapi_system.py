from pathlib import Path
from typing import Any

import pytest
import requests
from fastapi import status
from pydantic import TypeAdapter

from blueapi.client.client import (
    BlueapiClient,
    BlueskyRemoteControlError,
)
from blueapi.config import ApplicationConfig
from blueapi.service.model import (
    DeviceResponse,
    EnvironmentResponse,
    PlanResponse,
    TasksListResponse,
    WorkerTask,
)
from blueapi.worker.event import TaskStatusEnum, WorkerState
from blueapi.worker.task import Task
from blueapi.worker.task_worker import TrackableTask

_SIMPLE_TASK = Task(name="sleep", params={"time": 0.0})
_LONG_TASK = Task(name="sleep", params={"time": 1.0})

_DATA_PATH = Path(__file__).parent


@pytest.fixture
def client() -> BlueapiClient:
    return BlueapiClient.from_config(config=ApplicationConfig())


@pytest.fixture
def expected_plans() -> PlanResponse:
    return TypeAdapter(PlanResponse).validate_json(
        (_DATA_PATH / "plans.json").read_text()
    )


@pytest.fixture
def expected_devices() -> DeviceResponse:
    return TypeAdapter(DeviceResponse).validate_json(
        (_DATA_PATH / "devices.json").read_text()
    )


def get_response(
    url: str, BaseModel: Any, status_code: int = status.HTTP_200_OK
) -> Any:
    get_response = requests.get(url)
    model = TypeAdapter(BaseModel).validate_python(get_response.json())
    assert get_response.status_code == status_code
    return model


def test_get_plans(client: BlueapiClient, expected_plans: PlanResponse):
    assert client.get_plans() == expected_plans


def test_get_plans_by_name(client: BlueapiClient, expected_plans: PlanResponse):
    for plan in expected_plans.plans:
        assert client.get_plan(plan.name) == plan


def test_get_non_existent_plan(client: BlueapiClient):
    with pytest.raises(KeyError) as exception:
        client.get_plan("Not exists")
    assert exception.value.args[0] == ("{'detail': 'Item not found'}")


def test_get_devices(client: BlueapiClient, expected_devices: DeviceResponse):
    assert client.get_devices() == expected_devices


def test_get_device_by_name(client: BlueapiClient, expected_devices: DeviceResponse):
    for device in expected_devices.devices:
        assert client.get_device(device.name) == device


def test_get_non_existent_device(client: BlueapiClient):
    with pytest.raises(KeyError) as exception:
        assert client.get_device("Not exists")
    assert exception.value.args[0] == ("{'detail': 'Item not found'}")


def test_create_task_and_delete_task_by_id(client: BlueapiClient):
    create_task = client.create_task(_SIMPLE_TASK)
    client.clear_task(create_task.task_id)


def test_create_task_validation_error(client: BlueapiClient):
    with pytest.raises(KeyError) as exception:
        client.create_task(Task(name="Not-exists", params={"Not-exists": 0.0}))
    assert exception.value.args[0] == ("{'detail': 'Item not found'}")


def test_get_all_tasks(client: BlueapiClient):
    created_tasks = []
    for task in [_SIMPLE_TASK, _LONG_TASK]:
        created_task = client.create_task(task)
        created_tasks.append(created_task)

    task_list = get_response(client._rest._url("/tasks"), TasksListResponse)

    assert isinstance(task_list, TasksListResponse)
    task_ids = [task.task_id for task in created_tasks]
    for task in task_list.tasks:
        assert task.task_id in task_ids
        assert task.is_complete is False and task.is_pending is True

    for task in created_tasks:
        client.clear_task(task.task_id)


def test_get_task_by_id(client: BlueapiClient):
    created_task = client.create_task(_SIMPLE_TASK)

    get_task = client.get_task(created_task.task_id)
    assert (
        get_task.task_id == created_task.task_id
        and get_task.is_pending
        and not get_task.is_complete
        and len(get_task.errors) == 0
    )

    client.clear_task(created_task.task_id)


def test_get_non_existent_task(client: BlueapiClient):
    with pytest.raises(KeyError) as exception:
        client.get_task("Not-exists")
    assert exception.value.args[0] == "{'detail': 'Item not found'}"


def test_delete_non_existent_task(client: BlueapiClient):
    with pytest.raises(KeyError) as exception:
        client.clear_task("Not-exists")
    assert exception.value.args[0] == "{'detail': 'Item not found'}"


def test_put_worker_task(client: BlueapiClient):
    created_task = client.create_task(_SIMPLE_TASK)
    client.start_task(WorkerTask(task_id=created_task.task_id))
    active_task = client.get_active_task()
    assert active_task.task_id == created_task.task_id
    client.clear_task(created_task.task_id)


def test_put_worker_task_fails_if_not_idle(client: BlueapiClient):
    small_task = client.create_task(_SIMPLE_TASK)
    long_task = client.create_task(_LONG_TASK)

    client.start_task(WorkerTask(task_id=long_task.task_id))
    active_task = client.get_active_task()
    assert active_task.task_id == long_task.task_id

    with pytest.raises(BlueskyRemoteControlError) as exception:
        client.start_task(WorkerTask(task_id=small_task.task_id))
    assert exception.value.args[0] == "<Response [409]>"
    client.abort()
    client.clear_task(small_task.task_id)
    client.clear_task(long_task.task_id)


def test_get_worker_state(client: BlueapiClient):
    assert client.get_state() == WorkerState.IDLE


def test_set_state_transition_error(client: BlueapiClient):
    with pytest.raises(BlueskyRemoteControlError) as exception:
        client.resume()
    assert exception.value.args[0] == "<Response [400]>"

    with pytest.raises(BlueskyRemoteControlError) as exception:
        client.pause()
    assert exception.value.args[0] == "<Response [400]>"


def test_get_task_by_status(client: BlueapiClient):
    task_1 = client.create_task(_SIMPLE_TASK)
    task_2 = client.create_task(_SIMPLE_TASK)
    task_by_pending_request = requests.get(
        client._rest._url("/tasks"), params={"task_status": TaskStatusEnum.PENDING}
    )
    assert task_by_pending_request.status_code == status.HTTP_200_OK
    task_by_pending = TypeAdapter(TasksListResponse).validate_python(
        task_by_pending_request.json()
    )

    assert len(task_by_pending.tasks) == 2
    for task in task_by_pending.tasks:
        trackable_task = TypeAdapter(TrackableTask).validate_python(task)
        assert trackable_task.is_complete is False and trackable_task.is_pending is True

    client.start_task(WorkerTask(task_id=task_1.task_id))
    while not client.get_task(task_1.task_id).is_complete:
        ...
    client.start_task(WorkerTask(task_id=task_2.task_id))
    while not client.get_task(task_2.task_id).is_complete:
        ...
    task_by_completed_request = requests.get(
        client._rest._url("/tasks"), params={"task_status": TaskStatusEnum.COMPLETE}
    )
    task_by_completed = TypeAdapter(TasksListResponse).validate_python(
        task_by_completed_request.json()
    )
    assert len(task_by_completed.tasks) == 2
    for task in task_by_completed.tasks:
        trackable_task = TypeAdapter(TrackableTask).validate_python(task)
        assert trackable_task.is_complete is True and trackable_task.is_pending is False

    client.clear_task(task_id=task_1.task_id)
    client.clear_task(task_id=task_2.task_id)


def test_get_current_state_of_environment(client: BlueapiClient):
    assert client.get_environment() == EnvironmentResponse(initialized=True)


def test_delete_current_environment(client: BlueapiClient):
    client.reload_environment()
    assert client.get_environment() == EnvironmentResponse(initialized=True)

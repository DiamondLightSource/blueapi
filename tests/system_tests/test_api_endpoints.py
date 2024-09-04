import time
from typing import Any

import pytest
import requests
from fastapi import status
from pydantic import TypeAdapter

from blueapi.client.rest import BlueapiRestClient
from blueapi.service.interface import get_devices, get_plans
from blueapi.service.model import (
    DeviceResponse,
    EnvironmentResponse,
    PlanResponse,
    StateChangeRequest,
    TasksListResponse,
    WorkerTask,
)
from blueapi.worker.event import WorkerState
from blueapi.worker.task import Task
from blueapi.worker.task_worker import TrackableTask

_SIMPLE_TASK = Task(name="sleep", params={"time": 0.0})
_LONG_TASK = Task(name="sleep", params={"time": 1.0})

TASKS: list[Task] = [_SIMPLE_TASK, _LONG_TASK]

rest = BlueapiRestClient()


def get_response(
    url: str, BaseModel: Any, status_code: int = status.HTTP_200_OK
) -> Any:
    get_response = requests.get(url)
    model = TypeAdapter(BaseModel).validate_python(get_response.json())
    assert get_response.status_code == status_code
    return model


def post_response(
    url: str,
    json: dict[str, Any],
    BaseModel: Any,
    status_code: int = status.HTTP_201_CREATED,
) -> Any:
    post_response = requests.post(url, json=json)
    assert post_response.status_code == status_code
    return TypeAdapter(BaseModel).validate_python(post_response.json())


def delete_response(
    url: str, BaseModel: Any, status_code: int = status.HTTP_200_OK
) -> Any:
    delete_response = requests.delete(url)
    assert delete_response.status_code == status_code
    return TypeAdapter(BaseModel).validate_python(delete_response.json())


def put_response(
    url: str,
    data: str,
    BaseModel: Any,
    status_code: int = status.HTTP_200_OK,
) -> Any:
    put_response = requests.put(url, data=data)
    assert put_response.status_code == status_code
    return TypeAdapter(BaseModel).validate_python(put_response.json())


def test_get_plans():
    assert rest.get_plans() == PlanResponse(plans=get_plans())


def test_get_plans_by_name():
    for plan in get_plans():
        assert rest.get_plan(plan.name) == plan


def test_get_non_existant_plan():
    with pytest.raises(KeyError) as exception:
        rest.get_plan("Not exists")
    assert exception.value.args[0] == ("{'detail': 'Item not found'}")


def test_get_devices():
    assert rest.get_devices() == DeviceResponse(devices=get_devices())


def test_get_device_by_name():
    for device in get_devices():
        assert rest.get_device(device.name) == device


def test_get_non_existant_device():
    with pytest.raises(KeyError) as exception:
        assert rest.get_device("Not exists")
    assert exception.value.args[0] == ("{'detail': 'Item not found'}")


def test_post_task_and_delete_task_by_id():
    create_task = rest.create_task(_SIMPLE_TASK)
    rest.clear_task(create_task.task_id)


def test_get_tasks():
    created_tasks = []
    for task in TASKS:
        created_task = rest.create_task(task)
        created_tasks.append(created_task)

    task_list = get_response(rest._url("/tasks"), TasksListResponse)

    assert isinstance(task_list, TasksListResponse)
    task_ids = [task.task_id for task in created_tasks]
    for task in task_list.tasks:
        assert task.task_id in task_ids
        assert task.is_complete is False and task.is_pending is True

    for task in created_tasks:
        rest.clear_task(task.task_id)


def test_get_task_by_id():
    created_task = rest.create_task(_SIMPLE_TASK)

    get_task = rest.get_task(created_task.task_id)
    assert (
        get_task.task_id == created_task.task_id
        and get_task.is_pending
        and not get_task.is_complete
        and len(get_task.errors) == 0
    )

    rest.clear_task(created_task.task_id)


# TODO: Why are both these test the same
def test_get_worker_task_by_id():
    created_task = rest.create_task(_SIMPLE_TASK)

    get_task = rest.get_task(created_task.task_id)

    assert (
        isinstance(get_task, TrackableTask)
        and get_task.task_id == created_task.task_id
        and get_task.is_complete is False
        and get_task.is_pending is True
        and get_task.errors == []
    )

    rest.clear_task(created_task.task_id)


def test_put_worker_task():
    created_task = rest.create_task(_SIMPLE_TASK)
    rest.update_worker_task(WorkerTask(task_id=created_task.task_id))
    active_task = rest.get_active_task()
    assert active_task.task_id == created_task.task_id
    rest.clear_task(created_task.task_id)


def test_get_worker_state():
    assert rest.get_state() == WorkerState.IDLE


def test_put_worker_state():
    put_task = put_response(
        url=rest._url("/worker/state"),
        data=StateChangeRequest(new_state=WorkerState.RUNNING).model_dump_json(),
        BaseModel=WorkerState,
        status_code=status.HTTP_400_BAD_REQUEST,
    )
    assert isinstance(put_task, WorkerState)


def test_get_current_state_of_environment():
    assert rest.get_environment() == EnvironmentResponse(initialized=True)


def test_delete_current_environment():
    rest.delete_environment()
    time.sleep(5)
    assert rest.get_environment() == EnvironmentResponse(initialized=True)

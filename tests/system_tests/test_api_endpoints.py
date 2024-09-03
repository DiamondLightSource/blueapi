import asyncio
from typing import Any

import requests
from fastapi import status
from pydantic import TypeAdapter

from blueapi.config import RestConfig
from blueapi.service.interface import get_devices, get_plans
from blueapi.service.model import (
    DeviceModel,
    DeviceResponse,
    EnvironmentResponse,
    PlanModel,
    PlanResponse,
    TaskResponse,
    TasksListResponse,
)
from blueapi.worker.event import WorkerState
from blueapi.worker.task import Task
from blueapi.worker.task_worker import TrackableTask

ENDPOINT = f"{RestConfig().protocol}://{RestConfig().host}:{RestConfig().port}"

_SIMPLE_TASK = Task(name="sleep", params={"time": 0.0})
_LONG_TASK = Task(name="sleep", params={"time": 1.0})
_INDEFINITE_TASK = Task(
    name="set_absolute",
    params={"movable": "fake_device", "value": 4.0},
)
_FAILING_TASK = Task(name="failing_plan", params={})

TASKS: list[Task] = [_SIMPLE_TASK, _LONG_TASK]


def get_response(
    url: str, BaseModel: Any, status_code: int = status.HTTP_200_OK
) -> Any:
    get_response = requests.get(url)
    model = TypeAdapter(BaseModel).validate_python(get_response.json())
    assert get_response.status_code == status_code
    return model


def post_response(
    url: str, json: dict[str, Any], BaseModel: Any, status_code: int
) -> Any:
    post_response = requests.post(url, json=json)
    assert post_response.status_code == status_code
    return TypeAdapter(BaseModel).validate_python(post_response.json())


def delete_response(url: str, BaseModel: Any, status_code: int) -> Any:
    delete_response = requests.delete(url)
    assert delete_response.status_code == status_code
    return TypeAdapter(BaseModel).validate_python(delete_response.json())


def put_response(
    url: str, data: dict[str, str], BaseModel: Any, status_code: int
) -> Any:
    put_response = requests.put(url, data=data)
    assert put_response.status_code == status_code
    return TypeAdapter(BaseModel).validate_python(put_response.json())


def test_server_up():
    response = requests.get(ENDPOINT + "/docs")
    assert response.status_code == status.HTTP_200_OK


def test_get_current_state_of_environment():
    environment = get_response(ENDPOINT + "/environment", EnvironmentResponse)

    assert isinstance(
        environment, EnvironmentResponse
    ) and environment == EnvironmentResponse(initialized=True)


async def test_delete_current_environment():
    delete_response = requests.delete(ENDPOINT + "/environment")
    assert delete_response.status_code == status.HTTP_200_OK
    assert EnvironmentResponse(initialized=False).model_dump() == delete_response.json()
    await asyncio.sleep(5)
    get_response = requests.get(ENDPOINT + "/environment")
    assert get_response.status_code == status.HTTP_200_OK
    assert TypeAdapter(EnvironmentResponse).validate_python(
        get_response.json()
    ) == EnvironmentResponse(initialized=True)


def test_get_plans():
    get_plans_response = get_response(ENDPOINT + "/plans", PlanResponse)
    assert get_plans_response == PlanResponse(plans=get_plans())


def test_get_plans_by_name():
    for plan in get_plans():
        plan_response = get_response(f"{ENDPOINT}/plans/{plan.name}", PlanModel)
        assert plan_response == plan


def test_get_devices():
    get_device_response = get_response(ENDPOINT + "/devices", DeviceResponse)
    assert get_device_response == DeviceResponse(devices=get_devices())


def test_get_device_by_name():
    for device in get_devices():
        device_response = get_response(f"{ENDPOINT}/devices/{device.name}", DeviceModel)
        assert device_response == device


def test_post_task():
    post_response = requests.post(ENDPOINT + "/tasks", json=_SIMPLE_TASK.model_dump())
    assert post_response.status_code == status.HTTP_201_CREATED
    created_task = TypeAdapter(TaskResponse).validate_python(post_response.json())

    assert created_task

    delete_response = requests.delete(f"{ENDPOINT}/tasks/{created_task.task_id}")
    assert delete_response.status_code == status.HTTP_200_OK
    assert TypeAdapter(TaskResponse).validate_python(delete_response.json())


def test_get_tasks():
    created_tasks = []
    for task in TASKS:
        created_task = post_response(
            url=ENDPOINT + "/tasks",
            json=task.model_dump(),
            BaseModel=TaskResponse,
            status_code=status.HTTP_201_CREATED,
        )
        assert isinstance(created_task, TaskResponse)
        created_tasks.append(created_task)

    task_list = get_response(ENDPOINT + "/tasks", TasksListResponse)

    assert isinstance(task_list, TasksListResponse)
    task_ids = [task.task_id for task in created_tasks]
    for task in task_list.tasks:
        assert task.task_id in task_ids
        assert task.is_complete is False and task.is_pending is True

    for task in created_tasks:
        delete_response(
            url=f"{ENDPOINT}/tasks/{task.task_id}",
            BaseModel=TaskResponse,
            status_code=status.HTTP_200_OK,
        )


def test_delete_task_by_id():
    post_response = requests.post(ENDPOINT + "/tasks", json=_SIMPLE_TASK.model_dump())
    assert post_response.status_code == status.HTTP_201_CREATED
    created_task = TypeAdapter(TaskResponse).validate_python(post_response.json())

    assert created_task

    delete_response = requests.delete(f"{ENDPOINT}/tasks/{created_task.task_id}")
    assert delete_response.status_code == status.HTTP_200_OK
    assert TypeAdapter(TaskResponse).validate_python(delete_response.json())


def test_get_task_by_id():
    post_response = requests.post(ENDPOINT + "/tasks", json=_SIMPLE_TASK.model_dump())
    assert post_response.status_code == status.HTTP_201_CREATED
    created_task = TypeAdapter(TaskResponse).validate_python(post_response.json())

    assert created_task

    get_response = requests.get(f"{ENDPOINT}/tasks/{created_task.task_id}")
    assert get_response.status_code == status.HTTP_200_OK
    get_task = TypeAdapter(TrackableTask).validate_python(get_response.json())

    assert (
        get_task.task_id == created_task.task_id
        and get_task.is_pending
        and not get_task.is_complete
        and len(get_task.errors) == 0
    )
    delete_response = requests.delete(f"{ENDPOINT}/tasks/{created_task.task_id}")
    assert delete_response.status_code == status.HTTP_200_OK
    assert TypeAdapter(TaskResponse).validate_python(delete_response.json())


def test_get_worker_task_by_id():
    created_task = post_response(
        url=ENDPOINT + "/tasks",
        json=_SIMPLE_TASK.model_dump(),
        BaseModel=TaskResponse,
        status_code=status.HTTP_201_CREATED,
    )
    assert isinstance(created_task, TaskResponse)

    get_worker_info = get_response(
        f"{ENDPOINT}/tasks/{created_task.task_id}", TrackableTask
    )

    assert (
        isinstance(get_worker_info, TrackableTask)
        and get_worker_info.task_id == created_task.task_id
        and get_worker_info.is_complete is False
        and get_worker_info.is_pending is True
        and get_worker_info.errors == []
    )
    get_worker_state = get_response(ENDPOINT + "/worker/state", WorkerState)

    assert (
        isinstance(get_worker_state, WorkerState)
        and get_worker_state is WorkerState.IDLE
    )
    delete_response(
        url=f"{ENDPOINT}/tasks/{created_task.task_id}",
        BaseModel=TaskResponse,
        status_code=status.HTTP_200_OK,
    )


def test_put_worker_task():
    created_task = post_response(
        url=ENDPOINT + "/tasks",
        json=_SIMPLE_TASK.model_dump(),
        BaseModel=TaskResponse,
        status_code=status.HTTP_201_CREATED,
    )
    assert isinstance(created_task, TaskResponse)

    get_worker_info = get_response(
        f"{ENDPOINT}/tasks/{created_task.task_id}", TrackableTask
    )

    assert (
        isinstance(get_worker_info, TrackableTask)
        and get_worker_info.task_id == created_task.task_id
        and get_worker_info.is_complete is False
        and get_worker_info.is_pending is True
        and get_worker_info.errors == []
    )
    get_worker_state = get_response(ENDPOINT + "/worker/state", WorkerState)

    assert (
        isinstance(get_worker_state, WorkerState)
        and get_worker_state is WorkerState.IDLE
    )
    delete_response(
        url=f"{ENDPOINT}/tasks/{created_task.task_id}",
        BaseModel=TaskResponse,
        status_code=status.HTTP_200_OK,
    )


def test_get_worker_state(): ...


def test_put_worker_state(): ...

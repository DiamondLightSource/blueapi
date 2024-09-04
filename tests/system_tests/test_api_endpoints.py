import time
from typing import Any

import pytest
import requests
from fastapi import status
from pydantic import TypeAdapter

from blueapi.client.rest import BlueapiRestClient, BlueskyRemoteControlError
from blueapi.service.interface import get_devices, get_plans
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

rest = BlueapiRestClient()


def get_response(
    url: str, BaseModel: Any, status_code: int = status.HTTP_200_OK
) -> Any:
    get_response = requests.get(url)
    model = TypeAdapter(BaseModel).validate_python(get_response.json())
    assert get_response.status_code == status_code
    return model


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


def test_create_task_and_delete_task_by_id():
    create_task = rest.create_task(_SIMPLE_TASK)
    rest.clear_task(create_task.task_id)


def test_create_task_validation_error():
    with pytest.raises(KeyError) as exception:
        rest.create_task(Task(name="Not-exists", params={"Not-exists": 0.0}))
    assert exception.value.args[0] == ("{'detail': 'Item not found'}")


def test_get_all_tasks():
    created_tasks = []
    for task in [_SIMPLE_TASK, _LONG_TASK]:
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


def test_put_worker_task():
    created_task = rest.create_task(_SIMPLE_TASK)
    rest.update_worker_task(WorkerTask(task_id=created_task.task_id))
    active_task = rest.get_active_task()
    assert active_task.task_id == created_task.task_id
    rest.clear_task(created_task.task_id)


def test_put_worker_task_fails_if_not_idle():
    small_task = rest.create_task(_SIMPLE_TASK)
    long_task = rest.create_task(_LONG_TASK)

    rest.update_worker_task(WorkerTask(task_id=long_task.task_id))
    active_task = rest.get_active_task()
    assert active_task.task_id == long_task.task_id

    with pytest.raises(BlueskyRemoteControlError) as exception:
        rest.update_worker_task(WorkerTask(task_id=small_task.task_id))
    assert exception.value.args[0] == "<Response [409]>"
    time.sleep(1)
    rest.clear_task(small_task.task_id)
    rest.clear_task(long_task.task_id)


def test_get_worker_state():
    assert rest.get_state() == WorkerState.IDLE


def test_set_state_transition_error():
    with pytest.raises(BlueskyRemoteControlError) as exception:
        rest.set_state(WorkerState.RUNNING)
    assert exception.value.args[0] == "<Response [400]>"

    with pytest.raises(BlueskyRemoteControlError) as exception:
        rest.set_state(WorkerState.PAUSED)
    assert exception.value.args[0] == "<Response [400]>"


def test_get_task_by_status():
    task_1 = rest.create_task(_SIMPLE_TASK)
    task_2 = rest.create_task(_SIMPLE_TASK)
    task_by_pending_request = requests.get(
        rest._url("/tasks"), params={"task_status": TaskStatusEnum.PENDING}
    )
    assert task_by_pending_request.status_code == status.HTTP_200_OK
    task_by_pending = TypeAdapter(TasksListResponse).validate_python(
        task_by_pending_request.json()
    )

    assert len(task_by_pending.tasks) == 2
    for task in task_by_pending.tasks:
        trackable_task = TypeAdapter(TrackableTask).validate_python(task)
        assert trackable_task.is_complete is False and trackable_task.is_pending is True

    rest.update_worker_task(WorkerTask(task_id=task_1.task_id))
    time.sleep(0.1)
    rest.update_worker_task(WorkerTask(task_id=task_2.task_id))
    time.sleep(0.1)
    task_by_completed_request = requests.get(
        rest._url("/tasks"), params={"task_status": TaskStatusEnum.COMPLETE}
    )
    task_by_completed = TypeAdapter(TasksListResponse).validate_python(
        task_by_completed_request.json()
    )
    assert len(task_by_completed.tasks) == 2
    for task in task_by_completed.tasks:
        trackable_task = TypeAdapter(TrackableTask).validate_python(task)
        assert trackable_task.is_complete is True and trackable_task.is_pending is False

    rest.clear_task(task_id=task_1.task_id)
    rest.clear_task(task_id=task_2.task_id)


def test_get_current_state_of_environment():
    assert rest.get_environment() == EnvironmentResponse(initialized=True)


def test_delete_current_environment():
    rest.delete_environment()
    time.sleep(5)
    assert rest.get_environment() == EnvironmentResponse(initialized=True)

import uuid
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError
from pydantic.error_wrappers import ErrorWrapper
from super_state_machine.errors import TransitionError

from blueapi.core.bluesky_types import Plan
from blueapi.service import main
from blueapi.service.model import (
    DeviceModel,
    PlanModel,
    StateChangeRequest,
    WorkerTask,
)
from blueapi.worker.event import WorkerState
from blueapi.worker.task import Task
from blueapi.worker.worker import TrackableTask


@pytest.fixture
def client() -> TestClient:
 #   with (
 #       patch("blueapi.service.runner.worker"),
        #patch("blueapi.service.runner.stop_worker"),
  #  ):
    main.setup_handler(use_subprocess=False)
    yield TestClient(main.app)
    main.teardown_handler()


@patch("blueapi.service.interface.get_plans")
def test_get_plans(get_plans_mock: MagicMock, client: TestClient) -> None:
    class MyModel(BaseModel):
        id: str

    plan = Plan(name="my-plan", model=MyModel)
    get_plans_mock.return_value = [PlanModel.from_plan(plan)]

    response = client.get("/plans")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "plans": [
            {
                "description": None,
                "name": "my-plan",
                "schema": {
                    "properties": {"id": {"title": "Id", "type": "string"}},
                    "required": ["id"],
                    "title": "MyModel",
                    "type": "object",
                },
            }
        ]
    }


@patch("blueapi.service.interface.get_plan")
def test_get_plan_by_name(get_plan_mock: MagicMock, client: TestClient) -> None:
    class MyModel(BaseModel):
        id: str

    plan = Plan(name="my-plan", model=MyModel)
    get_plan_mock.return_value = PlanModel.from_plan(plan)

    response = client.get("/plans/my-plan")

    get_plan_mock.assert_called_once_with("my-plan")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "description": None,
        "name": "my-plan",
        "schema": {
            "properties": {"id": {"title": "Id", "type": "string"}},
            "required": ["id"],
            "title": "MyModel",
            "type": "object",
        },
    }


@patch("blueapi.service.interface.get_plan")
def test_get_non_existant_plan_by_name(
    get_plan_mock: MagicMock, client: TestClient
) -> None:
    get_plan_mock.side_effect = KeyError("my-plan")
    response = client.get("/plans/my-plan")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Item not found"}


@patch("blueapi.service.interface.get_devices")
def test_get_devices(get_devices_mock: MagicMock, client: TestClient) -> None:
    @dataclass
    class MyDevice:
        name: str

    device = MyDevice("my-device")
    get_devices_mock.return_value = [DeviceModel.from_device(device)]

    response = client.get("/devices")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "devices": [
            {
                "name": "my-device",
                "protocols": ["HasName"],
            }
        ]
    }


@patch("blueapi.service.interface.get_device")
def test_get_device_by_name(get_device_mock: MagicMock, client: TestClient) -> None:
    @dataclass
    class MyDevice:
        name: str

    device = MyDevice("my-device")

    get_device_mock.return_value = DeviceModel.from_device(device)
    response = client.get("/devices/my-device")

    get_device_mock.assert_called_once_with("my-device")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "name": "my-device",
        "protocols": ["HasName"],
    }


@patch("blueapi.service.interface.get_device")
def test_get_non_existent_device_by_name(
    get_device_mock: MagicMock, client: TestClient
) -> None:
    get_device_mock.side_effect = KeyError("my-device")
    response = client.get("/devices/my-device")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Item not found"}


@patch("blueapi.service.interface.submit_task")
@patch("blueapi.service.interface.get_plan")
def test_create_task(
    get_plan_mock: MagicMock, submit_task_mock: MagicMock, client: TestClient
) -> None:
    task = Task(name="count", params={"detectors": ["x"]})
    task_id = str(uuid.uuid4())

    submit_task_mock.return_value = task_id

    response = client.post("/tasks", json=task.dict())

    submit_task_mock.assert_called_once_with(task)
    assert response.json() == {"task_id": task_id}


@patch("blueapi.service.interface.submit_task")
@patch("blueapi.service.interface.get_plan")
def test_create_task_validation_error(
    get_plan_mock: MagicMock, submit_task_mock: MagicMock, client: TestClient
) -> None:
    class MyModel(BaseModel):
        id: str

    plan = Plan(name="my-plan", model=MyModel)
    get_plan_mock.return_value = PlanModel.from_plan(plan)

    submit_task_mock.side_effect = ValidationError(
        [ErrorWrapper(ValueError("field required"), "id")], PlanModel
    )

    response = client.post("/tasks", json={"name": "my-plan"})
    assert response.status_code == 422
    assert response.json() == {
        "detail": "\n"
        "        Input validation failed: id: field required,\n"
        "        suppplied params {},\n"
        "        do not match the expected params: {'title': 'MyModel', "
        "'type': 'object', 'properties': {'id': {'title': 'Id', 'type': "
        "'string'}}, 'required': ['id']}\n"
        "        "
    }


@patch("blueapi.service.interface.get_tasks")
def test_get_tasks(get_tasks_mock: MagicMock, client: TestClient) -> None:
    tasks = [
        TrackableTask(task_id="0", task=Task(name="sleep", params={"time": 0.0})),
        TrackableTask(
            task_id="1",
            task=Task(name="first_task"),
            is_complete=False,
            is_pending=True,
        ),
    ]

    get_tasks_mock.return_value = tasks

    response = client.get("/tasks")
    assert response.status_code == status.HTTP_200_OK

    assert response.json() == {
        "tasks": [
            {
                "errors": [],
                "is_complete": False,
                "is_pending": True,
                "task": {"name": "sleep", "params": {"time": 0.0}},
                "task_id": "0",
            },
            {
                "errors": [],
                "is_complete": False,
                "is_pending": True,
                "task": {"name": "first_task", "params": {}},
                "task_id": "1",
            },
        ]
    }


@patch("blueapi.service.interface.get_tasks_by_status")
def test_get_tasks_by_status(
    get_tasks_by_status_mock: MagicMock, client: TestClient
) -> None:
    tasks = [
        TrackableTask(
            task_id="3",
            task=Task(name="third_task"),
            is_complete=True,
            is_pending=False,
        ),
    ]

    get_tasks_by_status_mock.return_value = tasks

    response = client.get("/tasks", params={"task_status": "PENDING"})
    assert response.json() == {
        "tasks": [
            {
                "errors": [],
                "is_complete": True,
                "is_pending": False,
                "task": {"name": "third_task", "params": {}},
                "task_id": "3",
            }
        ]
    }


def test_get_tasks_by_status_invalid(client: TestClient) -> None:
    response = client.get("/tasks", params={"task_status": "AN_INVALID_STATUS"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@patch("blueapi.service.interface.clear_task")
def test_delete_submitted_task(clear_task_mock: MagicMock, client: TestClient) -> None:
    task_id = str(uuid.uuid4())
    clear_task_mock.return_value = task_id
    response = client.delete(f"/tasks/{task_id}")
    assert response.json() == {"task_id": f"{task_id}"}


@patch("blueapi.service.interface.begin_task")
@patch("blueapi.service.interface.get_active_task")
def test_set_active_task(
    get_active_task_mock: MagicMock, begin_task_mock: MagicMock, client: TestClient
) -> None:
    task_id = str(uuid.uuid4())
    task = WorkerTask(task_id=task_id)

    response = client.put("/worker/task", json=task.dict())

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"task_id": f"{task_id}"}


@patch("blueapi.service.interface.begin_task")
@patch("blueapi.service.interface.get_active_task")
def test_set_active_task_active_task_complete(
    get_active_task_mock: MagicMock, begin_task_mock: MagicMock, client: TestClient
) -> None:
    task_id = str(uuid.uuid4())
    task = WorkerTask(task_id=task_id)

    get_active_task_mock.return_value = TrackableTask(
        task_id="1",
        task=Task(name="a_completed_task"),
        is_complete=True,
        is_pending=False,
    )

    response = client.put("/worker/task", json=task.dict())

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"task_id": f"{task_id}"}


@patch("blueapi.service.interface.begin_task")
@patch("blueapi.service.interface.get_active_task")
def test_set_active_task_worker_already_running(
    get_active_task_mock: MagicMock, begin_task_mock: MagicMock, client: TestClient
) -> None:
    task_id = str(uuid.uuid4())
    task = WorkerTask(task_id=task_id)

    get_active_task_mock.return_value = TrackableTask(
        task_id="1",
        task=Task(name="a_running_task"),
        is_complete=False,
        is_pending=False,
    )

    response = client.put("/worker/task", json=task.dict())

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"detail": "Worker already active"}


@patch("blueapi.service.interface.get_task_by_id")
def test_get_task(get_task_by_id: MagicMock, client: TestClient):
    task_id = str(uuid.uuid4())
    task = TrackableTask(
        task_id=task_id,
        task=Task(name="third_task"),
    )

    get_task_by_id.return_value = task

    response = client.get(f"/tasks/{task_id}")
    assert response.json() == {
        "errors": [],
        "is_complete": False,
        "is_pending": True,
        "task": {"name": "third_task", "params": {}},
        "task_id": f"{task_id}",
    }


@patch("blueapi.service.interface.get_task_by_id")
def test_get_task_error(get_task_by_id_mock: MagicMock, client: TestClient):
    task_id = 567
    get_task_by_id_mock.return_value = None

    response = client.get(f"/tasks/{task_id}")
    assert response.json() == {"detail": "Item not found"}


@patch("blueapi.service.interface.get_active_task")
def test_get_active_task(get_active_task_mock: MagicMock, client: TestClient):
    task_id = str(uuid.uuid4())
    task = TrackableTask(
        task_id=task_id,
        task=Task(name="third_task"),
    )
    get_active_task_mock.return_value = task

    response = client.get("/worker/task")

    assert response.json() == {"task_id": f"{task_id}"}


@patch("blueapi.service.interface.get_active_task")
def test_get_active_task_none(get_active_task_mock: MagicMock, client: TestClient):
    get_active_task_mock.return_value = None

    response = client.get("/worker/task")

    assert response.json() == {"task_id": None}


@patch("blueapi.service.interface.get_worker_state")
def test_get_state(get_worker_state_mock: MagicMock, client: TestClient):
    state = WorkerState.SUSPENDING
    get_worker_state_mock.return_value = state

    response = client.get("/worker/state")
    assert response.json() == state


@patch("blueapi.service.interface.pause_worker")
@patch("blueapi.service.interface.get_worker_state")
def test_set_state_running_to_paused(
    get_worker_state_mock: MagicMock, pause_worker_mock: MagicMock, client: TestClient
):
    current_state = WorkerState.RUNNING
    final_state = WorkerState.PAUSED
    get_worker_state_mock.side_effect = [current_state, final_state]

    response = client.put(
        "/worker/state", json=StateChangeRequest(new_state=final_state).dict()
    )

    pause_worker_mock.assert_called_once_with(False)
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json() == final_state


@patch("blueapi.service.interface.resume_worker")
@patch("blueapi.service.interface.get_worker_state")
def test_set_state_paused_to_running(
    get_worker_state_mock: MagicMock, resume_worker_mock: MagicMock, client: TestClient
):
    current_state = WorkerState.PAUSED
    final_state = WorkerState.RUNNING
    get_worker_state_mock.side_effect = [current_state, final_state]

    response = client.put(
        "/worker/state", json=StateChangeRequest(new_state=final_state).dict()
    )

    resume_worker_mock.assert_called_once()
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json() == final_state


@patch("blueapi.service.interface.cancel_active_task")
@patch("blueapi.service.interface.get_worker_state")
def test_set_state_running_to_aborting(
    get_worker_state_mock: MagicMock,
    cancel_active_task_mock: MagicMock,
    client: TestClient,
):
    current_state = WorkerState.RUNNING
    final_state = WorkerState.ABORTING
    get_worker_state_mock.side_effect = [current_state, final_state]

    response = client.put(
        "/worker/state", json=StateChangeRequest(new_state=final_state).dict()
    )

    cancel_active_task_mock.assert_called_once_with(True, None)
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json() == final_state


@patch("blueapi.service.interface.cancel_active_task")
@patch("blueapi.service.interface.get_worker_state")
def test_set_state_running_to_stopping_including_reason(
    get_worker_state_mock: MagicMock,
    cancel_active_task_mock: MagicMock,
    client: TestClient,
):
    current_state = WorkerState.RUNNING
    final_state = WorkerState.STOPPING
    reason = "blueapi is being stopped"
    get_worker_state_mock.side_effect = [current_state, final_state]

    response = client.put(
        "/worker/state",
        json=StateChangeRequest(new_state=final_state, reason=reason).dict(),
    )

    cancel_active_task_mock.assert_called_once_with(False, reason)
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json() == final_state


@patch("blueapi.service.interface.cancel_active_task")
@patch("blueapi.service.interface.get_worker_state")
def test_set_state_transition_error(
    get_worker_state_mock: MagicMock,
    cancel_active_task_mock: MagicMock,
    client: TestClient,
):
    current_state = WorkerState.RUNNING
    final_state = WorkerState.STOPPING

    get_worker_state_mock.side_effect = [current_state, final_state]

    cancel_active_task_mock.side_effect = TransitionError()

    response = client.put(
        "/worker/state",
        json=StateChangeRequest(new_state=final_state).dict(),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == final_state


@patch("blueapi.service.interface.get_worker_state")
def test_set_state_invalid_transition(
    get_worker_state_mock: MagicMock, client: TestClient
):
    current_state = WorkerState.STOPPING
    requested_state = WorkerState.PAUSED
    final_state = WorkerState.STOPPING

    get_worker_state_mock.side_effect = [current_state, final_state]

    response = client.put(
        "/worker/state",
        json=StateChangeRequest(new_state=requested_state).dict(),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == final_state

from dataclasses import dataclass
from unittest.mock import MagicMock, patch
import uuid
from pydantic import BaseModel, ValidationError
from pydantic.error_wrappers import ErrorWrapper
import pytest
from blueapi.core.bluesky_types import Plan
from blueapi.service import interface

from dls_bluesky_core.plans import count
from fastapi.testclient import TestClient

from fastapi import status

from blueapi.service.model import DeviceModel, DeviceResponse, PlanModel
from blueapi.worker.task import Task
from blueapi.service import main
from fastapi.testclient import TestClient

from blueapi.worker.worker import TrackableTask


@pytest.fixture
def client() -> TestClient:
    with patch("blueapi.service.runner.start_worker"):
        with patch("blueapi.service.runner.stop_worker"):
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

def test_get_tasks_by_status_invalid(client: TestClient
) -> None:
    response = client.get("/tasks", params={"task_status": "AN_INVALID_STATUS"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@patch("blueapi.service.interface.clear_task")
def test_delete_submitted_task(clear_task_mock: MagicMock, client: TestClient) -> None:
    task_id = str(uuid.uuid4())
    clear_task_mock.return_value = task_id
    response = client.delete(f"/tasks/{task_id}")
    assert response.json() == {"task_id": f"{task_id}"}

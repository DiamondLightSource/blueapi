from dataclasses import dataclass

from bluesky.run_engine import RunEngineStateMachine
from fastapi.testclient import TestClient
from pydantic import BaseModel

from blueapi.core.bluesky_types import Plan
from blueapi.service.handler import Handler
from blueapi.worker.task import RunPlan
from src.blueapi.worker import WorkerState

_TASK = RunPlan(name="count", params={"detectors": ["x"]})


def test_get_plans(handler: Handler, client: TestClient) -> None:
    class MyModel(BaseModel):
        id: str

    plan = Plan(name="my-plan", model=MyModel)

    handler.context.plans = {"my-plan": plan}
    response = client.get("/plans")

    assert response.status_code == 200
    assert response.json() == {"plans": [{"name": "my-plan"}]}


def test_get_plan_by_name(handler: Handler, client: TestClient) -> None:
    class MyModel(BaseModel):
        id: str

    plan = Plan(name="my-plan", model=MyModel)

    handler.context.plans = {"my-plan": plan}
    response = client.get("/plans/my-plan")

    assert response.status_code == 200
    assert response.json() == {"name": "my-plan"}


def test_get_devices(handler: Handler, client: TestClient) -> None:
    @dataclass
    class MyDevice:
        name: str

    device = MyDevice("my-device")

    handler.context.devices = {"my-device": device}
    response = client.get("/devices")

    assert response.status_code == 200
    assert response.json() == {
        "devices": [
            {
                "name": "my-device",
                "protocols": ["HasName"],
            }
        ]
    }


def test_get_device_by_name(handler: Handler, client: TestClient) -> None:
    @dataclass
    class MyDevice:
        name: str

    device = MyDevice("my-device")

    handler.context.devices = {"my-device": device}
    response = client.get("/devices/my-device")

    assert response.status_code == 200
    assert response.json() == {
        "name": "my-device",
        "protocols": ["HasName"],
    }


def test_create_task(handler: Handler, client: TestClient) -> None:
    response = client.post("/tasks", json=_TASK.dict())
    task_id = response.json()["taskId"]
    assert handler.worker.get_pending_task(task_id).task == _TASK


def test_put_plan_submits_task(handler: Handler, client: TestClient) -> None:
    task_name = "count"
    task_params = {"detectors": ["x"]}
    task_json = {"name": task_name, "params": task_params}

    client.post("/tasks", json=task_json)

    assert handler.worker.get_pending_tasks()[0].task == RunPlan(
        name=task_name, params=task_params
    )


def test_get_state_updates(handler: Handler, client: TestClient) -> None:
    assert client.get("/worker/state").text == f'"{WorkerState.IDLE.name}"'
    handler.worker._on_state_change(  # type: ignore
        RunEngineStateMachine.States.RUNNING
    )
    assert client.get("/worker/state").text == f'"{WorkerState.RUNNING.name}"'

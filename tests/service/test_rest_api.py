from dataclasses import dataclass

from fastapi.testclient import TestClient
from pydantic import BaseModel

from blueapi.core.bluesky_types import Plan
from blueapi.service.handler import Handler
from blueapi.worker.task import RunPlan, Task


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
    response = client.get("/plan/my-plan")

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
    response = client.get("/device/my-device")

    assert response.status_code == 200
    assert response.json() == {
        "name": "my-device",
        "protocols": ["HasName"],
    }


def test_put_plan_submits_task(handler: Handler, client: TestClient) -> None:
    task_json = {"detectors": ["x"]}
    task_name = "count"
    submitted_tasks = {}

    def on_submit(name: str, task: Task):
        submitted_tasks[name] = task

    handler.worker.submit_task.side_effect = on_submit  # type: ignore

    client.put(f"/task/{task_name}", json=task_json)
    assert submitted_tasks == {task_name: RunPlan(name=task_name, params=task_json)}

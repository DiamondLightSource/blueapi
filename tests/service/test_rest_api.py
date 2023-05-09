from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from mock import Mock
from pydantic import BaseModel

from blueapi.core.bluesky_types import Plan
from blueapi.core.context import BlueskyContext
from blueapi.service.handler import get_handler
from blueapi.service.main import app
from blueapi.worker import RunEngineWorker
from blueapi.worker.task import RunPlan, Task


class MockHandler:
    context: BlueskyContext
    worker: RunEngineWorker

    def __init__(self) -> None:
        self.context = Mock()
        self.worker = Mock()


class Client:
    handler = None

    def __init__(self, handler: MockHandler) -> None:
        """Create tester object"""
        self.handler = handler

    @property
    def client(self) -> TestClient:
        app.dependency_overrides[get_handler] = lambda: self.handler
        return TestClient(app)


@pytest.fixture
def handler() -> MockHandler:
    return MockHandler()


@pytest.fixture
def client(handler: MockHandler) -> TestClient:
    return Client(handler).client


def test_get_plans(handler: MockHandler, client: TestClient) -> None:
    class MyModel(BaseModel):
        id: str

    plan = Plan(name="my-plan", model=MyModel)

    handler.context.plans = {"my-plan": plan}
    response = client.get("/plans")

    assert response.status_code == 200
    assert response.json() == {"plans": [{"name": "my-plan"}]}


def test_get_plan_by_name(handler: MockHandler, client: TestClient) -> None:
    class MyModel(BaseModel):
        id: str

    plan = Plan(name="my-plan", model=MyModel)

    handler.context.plans = {"my-plan": plan}
    response = client.get("/plan/my-plan")

    assert response.status_code == 200
    assert response.json() == {"name": "my-plan"}


def test_get_devices(handler: MockHandler, client: TestClient) -> None:
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


def test_get_device_by_name(handler: MockHandler, client: TestClient) -> None:
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


def test_put_plan_submits_task(handler: MockHandler, client: TestClient) -> None:
    task_json = {"detectors": ["x"]}
    task_name = "count"
    submitted_tasks = {}

    def on_submit(name: str, task: Task):
        submitted_tasks[name] = task

    handler.worker.submit_task.side_effect = on_submit

    client.put(f"/task/{task_name}", json=task_json)
    assert submitted_tasks == {task_name: RunPlan(name=task_name, params=task_json)}

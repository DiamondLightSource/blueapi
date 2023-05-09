from ast import literal_eval
from dataclasses import dataclass

from fastapi.testclient import TestClient
from pydantic import BaseModel

from blueapi.core.bluesky_types import Plan
from blueapi.core.context import BlueskyContext
from blueapi.service.handler import get_handler
from blueapi.service.main import app
from blueapi.worker import RunEngineWorker
from blueapi.worker.task import ActiveTask


class MockHandler:
    context: BlueskyContext
    worker: RunEngineWorker

    def __init__(self) -> None:
        self.context = BlueskyContext()
        self.worker = RunEngineWorker(self.context)


class Client:
    def __init__(self, handler: MockHandler) -> None:
        """Create tester object"""
        self.handler = handler

    @property
    def client(self) -> TestClient:
        app.dependency_overrides[get_handler] = lambda: self.handler
        return TestClient(app)


def test_get_plans() -> None:
    handler = MockHandler()
    client = Client(handler).client

    class MyModel(BaseModel):
        id: str

    plan = Plan(name="my-plan", model=MyModel)

    handler.context.plans = {"my-plan": plan}
    response = client.get("/plans")

    assert response.status_code == 200
    assert literal_eval(response.content.decode())["plans"][0] == {"name": "my-plan"}


def test_get_plan_by_name() -> None:
    handler = MockHandler()
    client = Client(handler).client

    class MyModel(BaseModel):
        id: str

    plan = Plan(name="my-plan", model=MyModel)

    handler.context.plans = {"my-plan": plan}
    response = client.get("/plan/my-plan")

    assert response.status_code == 200
    assert literal_eval(response.content.decode()) == {"name": "my-plan"}


def test_get_devices() -> None:
    handler = MockHandler()
    client = Client(handler).client

    @dataclass
    class MyDevice:
        name: str

    device = MyDevice("my-device")

    handler.context.devices = {"my-device": device}
    response = client.get("/devices")

    assert response.status_code == 200
    assert literal_eval(response.content.decode())["devices"][0] == {
        "name": "my-device",
        "protocols": ["HasName"],
    }


def test_get_device_by_name() -> None:
    handler = MockHandler()
    client = Client(handler).client

    @dataclass
    class MyDevice:
        name: str

    device = MyDevice("my-device")

    handler.context.devices = {"my-device": device}
    response = client.get("/device/my-device")

    assert response.status_code == 200
    assert literal_eval(response.content.decode()) == {
        "name": "my-device",
        "protocols": ["HasName"],
    }


def test_put_plan_on_queue() -> None:
    handler = MockHandler()
    client = Client(handler).client

    client.put("/task/my-task", json={"name": "count", "params": {"detectors": ["x"]}})
    next_task: ActiveTask = handler.worker._task_queue.get(timeout=1.0)

    assert next_task

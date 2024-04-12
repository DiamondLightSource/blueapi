import json
from dataclasses import dataclass
from unittest.mock import MagicMock, call

import pytest
from bluesky.run_engine import RunEngineStateMachine
from fastapi import status
from fastapi.testclient import TestClient
from pydantic import BaseModel

from blueapi.core.bluesky_types import Plan
from blueapi.service.handler import Handler
from blueapi.service.main import get_handler, setup_handler, teardown_handler
from blueapi.service.model import WorkerTask
from blueapi.worker import WorkerState
from blueapi.worker.task import Task

_TASK = Task(name="count", params={"detectors": ["x"]})


def test_get_plans(handler: Handler, client: TestClient) -> None:
    class MyModel(BaseModel):
        id: str

    plan = Plan(name="my-plan", model=MyModel)

    handler._context.plans = {"my-plan": plan}
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


def test_get_plan_by_name(handler: Handler, client: TestClient) -> None:
    class MyModel(BaseModel):
        id: str

    plan = Plan(name="my-plan", model=MyModel)

    handler._context.plans = {"my-plan": plan}
    response = client.get("/plans/my-plan")

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


def test_get_plan_with_device_reference(handler: Handler, client: TestClient) -> None:
    response = client.get("/plans/count")

    assert response.status_code == status.HTTP_200_OK
    assert (
        response.json()
        == {
            "description": "\n"
            "    Take `n` readings from a device\n"
            "\n"
            "    Args:\n"
            "        detectors (List[Readable]): Readable devices to read\n"
            "        num (int, optional): Number of readings to take. "
            "Defaults to 1.\n"
            "        delay (Optional[Union[float, List[float]]], "
            "optional): Delay between readings.\n"
            "                                                               "
            "Defaults to None.\n"
            "        metadata (Optional[Mapping[str, Any]], optional): "
            "Key-value metadata to include\n"
            "                                                          in "
            "exported data.\n"
            "                                                          "
            "Defaults to None.\n"
            "\n"
            "    Returns:\n"
            "        MsgGenerator: _description_\n"
            "\n"
            "    Yields:\n"
            "        Iterator[MsgGenerator]: _description_\n"
            "    ",
            "name": "count",
            "schema": {
                "additionalProperties": False,
                "properties": {
                    "delay": {
                        "anyOf": [
                            {"type": "number"},
                            {"items": {"type": "number"}, "type": "array"},
                        ],
                        "title": "Delay",
                    },
                    "detectors": {
                        "items": {
                            "_detectors": "<class " "'bluesky.protocols.Readable'>"
                        },
                        "title": "Detectors",
                        "type": "array",
                    },
                    "metadata": {"title": "Metadata", "type": "object"},
                    "num": {"title": "Num", "type": "integer"},
                },
                "required": ["detectors"],
                "title": "count",
                "type": "object",
            },
        }
        != {
            "name": "count",
            "properties": {
                "delay": {
                    "anyOf": [
                        {"type": "number"},
                        {"items": {"type": "number"}, "type": "array"},
                    ],
                    "title": "Delay",
                },
                "detectors": {
                    "items": {"_detectors": "<class " "'bluesky.protocols.Readable'>"},
                    "title": "Detectors",
                    "type": "array",
                },
                "metadata": {"title": "Metadata", "type": "object"},
                "num": {"title": "Num", "type": "integer"},
            },
            "required": ["detectors"],
        }
    )


def test_get_non_existant_plan_by_name(handler: Handler, client: TestClient) -> None:
    response = client.get("/plans/my-plan")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Item not found"}


def test_get_devices(handler: Handler, client: TestClient) -> None:
    @dataclass
    class MyDevice:
        name: str

    device = MyDevice("my-device")

    handler._context.devices = {"my-device": device}
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


def test_get_device_by_name(handler: Handler, client: TestClient) -> None:
    @dataclass
    class MyDevice:
        name: str

    device = MyDevice("my-device")

    handler._context.devices = {"my-device": device}
    response = client.get("/devices/my-device")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "name": "my-device",
        "protocols": ["HasName"],
    }


def test_get_non_existant_device_by_name(handler: Handler, client: TestClient) -> None:
    response = client.get("/devices/my-device")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Item not found"}


def test_create_task(handler: Handler, client: TestClient) -> None:
    response = client.post("/tasks", json=_TASK.dict())
    task_id = response.json()["task_id"]

    t = handler.get_task_by_id(task_id)
    assert t is not None
    assert t.task == _TASK


def test_put_plan_begins_task(handler: Handler, client: TestClient) -> None:
    handler.start()
    response = client.post("/tasks", json=_TASK.dict())
    task_id = response.json()["task_id"]

    task_json = {"task_id": task_id}
    client.put("/worker/task", json=task_json)

    resp = client.get("/worker/task")
    assert resp.status_code == 200
    active_task = WorkerTask(**resp.json())
    assert active_task is not None
    assert active_task.task_id == task_id
    handler.stop()


def test_worker_task_is_none_on_startup(handler: Handler, client: TestClient) -> None:
    handler.start()
    resp = client.get("/worker/task")
    assert resp.status_code == 200
    active_task = WorkerTask(**resp.json())
    assert active_task.task_id is None
    handler.stop()


def test_get_worker_task(handler: Handler, client: TestClient) -> None:
    handler.start()
    response = client.post("/tasks", json=_TASK.dict())
    task_id = response.json()["task_id"]

    task_json = {"task_id": task_id}
    client.put("/worker/task", json=task_json)

    active_task = handler.active_task
    assert active_task is not None
    assert active_task.task_id == task_id
    handler.stop()


def test_put_plan_with_unknown_plan_name_fails(
    handler: Handler, client: TestClient
) -> None:
    task_name = "foo"
    task_params = {"detectors": ["x"]}
    task_json = {"name": task_name, "params": task_params}

    response = client.post("/tasks", json=task_json)

    assert not handler.tasks
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_plan_returns_posted_plan(handler: Handler, client: TestClient) -> None:
    handler.start()
    post_response = client.post("/tasks", json=_TASK.dict())
    task_id = post_response.json()["task_id"]

    str_map = json.load(client.get(f"/tasks/{task_id}"))  # type: ignore

    assert str_map["task_id"] == task_id
    assert str_map["task"] == _TASK.dict()


def test_get_non_existant_plan_by_id(handler: Handler, client: TestClient) -> None:
    response = client.get("/tasks/foo")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Item not found"}


def test_put_plan_with_bad_params_fails(handler: Handler, client: TestClient) -> None:
    task_name = "count"
    task_params = {"motors": ["x"]}
    task_json = {"name": task_name, "params": task_params}

    response = client.post("/tasks", json=task_json)

    assert not handler.tasks
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_get_state_updates(handler: Handler, client: TestClient) -> None:
    assert client.get("/worker/state").text == f'"{WorkerState.IDLE.name}"'
    handler._worker._on_state_change(  # type: ignore
        RunEngineStateMachine.States.RUNNING
    )
    assert client.get("/worker/state").text == f'"{WorkerState.RUNNING.name}"'


@pytest.fixture
def mockable_state_machine(handler: Handler):
    def set_state(state: RunEngineStateMachine.States):
        handler._context.run_engine.state = state  # type: ignore
        handler._worker._on_state_change(state)  # type: ignore

    def pause(_: bool):
        set_state(RunEngineStateMachine.States.PAUSED)

    def run():
        set_state(RunEngineStateMachine.States.RUNNING)

    mock_pause = handler._context.run_engine.request_pause = MagicMock()  # type: ignore
    mock_pause.side_effect = pause
    mock_resume = handler._context.run_engine.resume = MagicMock()  # type: ignore
    mock_resume.side_effect = run
    yield handler


def test_running_while_idle_denied(
    mockable_state_machine: Handler, client: TestClient
) -> None:
    re = mockable_state_machine._context.run_engine

    assert client.get("/worker/state").text == f'"{WorkerState.IDLE.name}"'
    response = client.put("/worker/state", json={"new_state": WorkerState.RUNNING.name})
    assert response.status_code is status.HTTP_400_BAD_REQUEST
    assert response.text == f'"{WorkerState.IDLE.name}"'
    assert not re.request_pause.called  # type: ignore
    assert not re.resume.called  # type: ignore
    assert client.get("/worker/state").text == f'"{WorkerState.IDLE.name}"'


def test_pausing_while_idle_denied(
    mockable_state_machine: Handler, client: TestClient
) -> None:
    re = mockable_state_machine._context.run_engine

    assert client.get("/worker/state").text == f'"{WorkerState.IDLE.name}"'
    response = client.put("/worker/state", json={"new_state": WorkerState.PAUSED.name})
    assert response.status_code is status.HTTP_400_BAD_REQUEST
    assert response.text == f'"{WorkerState.IDLE.name}"'
    assert not re.request_pause.called  # type: ignore
    assert not re.resume.called  # type: ignore
    assert client.get("/worker/state").text == f'"{WorkerState.IDLE.name}"'


@pytest.mark.parametrize("defer", [True, False, None])
def test_calls_pause_if_running(
    mockable_state_machine: Handler, client: TestClient, defer: bool | None
) -> None:
    re = mockable_state_machine._context.run_engine
    mockable_state_machine._worker._on_state_change(  # type: ignore
        RunEngineStateMachine.States.RUNNING
    )

    assert client.get("/worker/state").text == f'"{WorkerState.RUNNING.name}"'
    response = client.put(
        "/worker/state", json={"new_state": WorkerState.PAUSED.name, "defer": defer}
    )
    assert response.status_code is status.HTTP_202_ACCEPTED
    assert response.text == f'"{WorkerState.PAUSED.name}"'
    assert re.request_pause.called  # type: ignore
    re.request_pause.assert_called_with(defer)  # type: ignore
    assert not re.resume.called  # type: ignore
    assert client.get("/worker/state").text == f'"{WorkerState.PAUSED.name}"'


def test_pause_and_resume(mockable_state_machine: Handler, client: TestClient) -> None:
    re = mockable_state_machine._context.run_engine
    mockable_state_machine._worker._on_state_change(  # type: ignore
        RunEngineStateMachine.States.RUNNING
    )

    assert client.get("/worker/state").text == f'"{WorkerState.RUNNING.name}"'
    response = client.put("/worker/state", json={"new_state": WorkerState.PAUSED.name})
    assert response.status_code is status.HTTP_202_ACCEPTED
    assert response.text == f'"{WorkerState.PAUSED.name}"'
    assert re.request_pause.call_count == 1  # type: ignore
    assert not re.resume.called  # type: ignore
    assert client.get("/worker/state").text == f'"{WorkerState.PAUSED.name}"'

    response = client.put("/worker/state", json={"new_state": WorkerState.RUNNING.name})
    assert response.status_code is status.HTTP_202_ACCEPTED
    assert response.text == f'"{WorkerState.RUNNING.name}"'
    assert re.request_pause.call_count == 1  # type: ignore
    assert re.resume.call_count == 1  # type: ignore
    assert client.get("/worker/state").text == f'"{WorkerState.RUNNING.name}"'


def test_clear_pending_task_no_longer_pending(handler: Handler, client: TestClient):
    response = client.post("/tasks", json=_TASK.dict())
    task_id = response.json()["task_id"]

    t = handler.get_task_by_id(task_id)
    assert t is not None
    assert t.task == _TASK

    delete_response = client.delete(f"/tasks/{task_id}")
    assert delete_response.status_code is status.HTTP_200_OK
    assert not handler.tasks
    assert handler.get_task_by_id(task_id) is None


def test_clear_not_pending_task_not_found(handler: Handler, client: TestClient):
    response = client.post("/tasks", json=_TASK.dict())
    task_id = response.json()["task_id"]

    pending = handler.get_task_by_id(task_id)
    assert pending is not None
    assert pending.task == _TASK

    delete_response = client.delete("/tasks/wrong-task-id")
    assert delete_response.status_code is status.HTTP_404_NOT_FOUND
    pending = handler.get_task_by_id(task_id)
    assert pending is not None
    assert pending.task == _TASK


def test_clear_when_empty(handler: Handler, client: TestClient):
    pending = handler.tasks
    assert not pending

    delete_response = client.delete("/tasks/wrong-task-id")
    assert delete_response.status_code is status.HTTP_404_NOT_FOUND
    assert not handler.tasks


@pytest.mark.parametrize(
    "worker_state,stops,aborts",
    [(WorkerState.STOPPING, 1, 0), (WorkerState.ABORTING, 0, 1)],
)
def test_delete_running_task(
    mockable_state_machine: Handler,
    client: TestClient,
    worker_state: WorkerState,
    stops: int,
    aborts: int,
):
    stop = mockable_state_machine._context.run_engine.stop = MagicMock()  # type: ignore
    abort = mockable_state_machine._context.run_engine.abort = (  # type: ignore
        MagicMock()
    )

    def start_task(_: str):
        mockable_state_machine._worker._current = (  # type: ignore
            mockable_state_machine._worker.get_task_by_id(task_id)
        )
        mockable_state_machine._worker._on_state_change(  # type: ignore
            RunEngineStateMachine.States.RUNNING
        )

    mockable_state_machine._worker.begin_task = start_task  # type: ignore
    response = client.post("/tasks", json=_TASK.dict())
    task_id = response.json()["task_id"]

    task_json = {"task_id": task_id}
    client.put("/worker/task", json=task_json)

    active_task = mockable_state_machine.active_task
    assert active_task is not None
    assert active_task.task_id == task_id

    response = client.put("/worker/state", json={"new_state": worker_state.name})
    assert response.status_code is status.HTTP_202_ACCEPTED
    assert stop.call_count is stops
    assert abort.call_count is aborts


def test_reason_passed_to_abort(mockable_state_machine: Handler, client: TestClient):
    abort = mockable_state_machine._context.run_engine.abort = (  # type: ignore
        MagicMock()
    )

    def start_task(_: str):
        mockable_state_machine._worker._current = (  # type: ignore
            mockable_state_machine._worker.get_task_by_id(task_id)
        )
        mockable_state_machine._worker._on_state_change(  # type: ignore
            RunEngineStateMachine.States.RUNNING
        )

    mockable_state_machine._worker.begin_task = start_task  # type: ignore
    response = client.post("/tasks", json=_TASK.dict())
    task_id = response.json()["task_id"]

    task_json = {"task_id": task_id}
    client.put("/worker/task", json=task_json)

    active_task = mockable_state_machine._worker.get_active_task()
    assert active_task is not None
    assert active_task.task_id == task_id

    response = client.put(
        "/worker/state", json={"new_state": WorkerState.ABORTING.name, "reason": "foo"}
    )
    assert response.status_code is status.HTTP_202_ACCEPTED
    assert abort.call_args == call("foo")


@pytest.mark.parametrize(
    "worker_state",
    [WorkerState.ABORTING, WorkerState.STOPPING],
)
def test_current_complete_returns_400(
    mockable_state_machine: Handler, client: TestClient, worker_state: WorkerState
):
    mockable_state_machine._worker._current = MagicMock()  # type: ignore
    mockable_state_machine._worker._current.is_complete = True  # type: ignore

    # As _current.is_complete, necessarily state of run_engine is IDLE
    response = client.put(
        "/worker/state", json={"new_state": WorkerState.ABORTING.name, "reason": "foo"}
    )
    assert response.status_code is status.HTTP_400_BAD_REQUEST


def test_get_environment(handler: Handler, client: TestClient) -> None:
    assert client.get("/environment").json() == {"initialized": False}


def test_delete_environment(handler: Handler, client: TestClient) -> None:
    handler._initialized = True
    assert client.delete("/environment").status_code is status.HTTP_200_OK


def test_teardown_handler():
    setup_handler()
    assert get_handler() is not None
    teardown_handler()
    with pytest.raises(ValueError):
        get_handler()


def test_teardown_handler_does_not_raise():
    assert teardown_handler() is None

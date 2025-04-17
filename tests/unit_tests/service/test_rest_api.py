import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from unittest.mock import MagicMock, Mock, patch

import jwt
import pytest
from bluesky.protocols import Stoppable
from fastapi import status
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError
from pydantic_core import InitErrorDetails
from super_state_machine.errors import TransitionError

from blueapi.config import ApplicationConfig, CORSConfig, OIDCConfig, RestConfig
from blueapi.core.bluesky_types import Plan
from blueapi.service import main
from blueapi.service.interface import (
    cancel_active_task,
    get_device,
    get_plan,
    pause_worker,
    resume_worker,
    submit_task,
)
from blueapi.service.model import (
    DeviceModel,
    EnvironmentResponse,
    PackageInfo,
    PlanModel,
    PythonEnvironmentResponse,
    SourceInfo,
    StateChangeRequest,
    WorkerTask,
)
from blueapi.service.runner import WorkerDispatcher
from blueapi.worker.event import WorkerState
from blueapi.worker.task import Task
from blueapi.worker.task_worker import TrackableTask


class MockCountModel(BaseModel): ...


COUNT = Plan(name="count", model=MockCountModel)


@pytest.fixture
def mock_runner() -> Mock:
    return Mock(spec=WorkerDispatcher)


@pytest.fixture
def client(mock_runner: Mock) -> Iterator[TestClient]:
    with patch("blueapi.service.interface.worker"):
        main.setup_runner(runner=mock_runner)
        yield TestClient(main.get_app(ApplicationConfig()))
        main.teardown_runner()


@pytest.fixture
def client_with_auth(
    mock_runner: Mock, oidc_config: OIDCConfig
) -> Iterator[TestClient]:
    with patch("blueapi.service.interface.worker"):
        main.setup_runner(runner=mock_runner)
        yield TestClient(main.get_app(ApplicationConfig(oidc=oidc_config)))
        main.teardown_runner()


@pytest.fixture
def rest_config_with_cors() -> RestConfig:
    cors_config = CORSConfig(
        origins=["http://testhost:8080"],
        allow_credentials=True,
        allow_methods=["*"],
    )
    return RestConfig(cors=cors_config)


@pytest.fixture
def client_with_cors(
    mock_runner: Mock, rest_config_with_cors: RestConfig
) -> Iterator[TestClient]:
    with patch("blueapi.service.interface.worker"):
        main.setup_runner(runner=mock_runner)
        yield TestClient(main.get_app(ApplicationConfig(api=rest_config_with_cors)))
        main.teardown_runner()


@dataclass
class MinimalDevice(Stoppable):
    name: str

    def stop(self, success: bool = True):
        pass


def test_rest_config_with_cors_gets_plan(
    client_with_cors: TestClient,
    mock_runner: Mock,
):
    class MyModel(BaseModel):
        id: str

    plan = Plan(name="my-plan", model=MyModel)
    mock_runner.run.return_value = [PlanModel.from_plan(plan)]

    response_get = client_with_cors.get("/plans")
    assert response_get.status_code == status.HTTP_200_OK


def test_rest_config_with_cors(
    client_with_cors: TestClient,
    mock_runner: Mock,
):
    task = Task(name="my-plan", params={"id": "x"})
    task_id = "f8424be3-203c-494e-b22f-219933b4fa67"
    mock_runner.run.side_effect = [task_id]
    HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}

    # Allowed method
    response_post = client_with_cors.post(
        "/tasks",
        json=task.model_dump(),
        headers=HEADERS,
    )
    assert response_post.status_code == status.HTTP_201_CREATED
    assert response_post.headers["content-type"] == "application/json"


def test_get_plans(mock_runner: Mock, client: TestClient) -> None:
    class MyModel(BaseModel):
        id: str

    plan = Plan(name="my-plan", model=MyModel)
    mock_runner.run.return_value = [PlanModel.from_plan(plan)]

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


def test_get_plan_by_name(mock_runner: Mock, client: TestClient) -> None:
    class MyModel(BaseModel):
        id: str

    plan = Plan(name="my-plan", model=MyModel)
    mock_runner.run.return_value = PlanModel.from_plan(plan)

    response = client.get("/plans/my-plan")

    mock_runner.run.assert_called_once_with(get_plan, "my-plan")
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


def test_get_non_existent_plan_by_name(mock_runner: Mock, client: TestClient) -> None:
    mock_runner.run.side_effect = KeyError("my-plan")
    response = client.get("/plans/my-plan")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Item not found"}


def test_get_devices(mock_runner: Mock, client: TestClient) -> None:
    device = MinimalDevice("my-device")
    mock_runner.run.return_value = [DeviceModel.from_device(device)]

    response = client.get("/devices")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "devices": [
            {
                "name": "my-device",
                "protocols": [{"name": "Stoppable", "types": []}],
            }
        ]
    }


def test_get_device_by_name(mock_runner: Mock, client: TestClient) -> None:
    device = MinimalDevice("my-device")

    mock_runner.run.return_value = DeviceModel.from_device(device)
    response = client.get("/devices/my-device")

    mock_runner.run.assert_called_once_with(get_device, "my-device")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "name": "my-device",
        "protocols": [{"name": "Stoppable", "types": []}],
    }


def test_get_non_existent_device_by_name(mock_runner: Mock, client: TestClient) -> None:
    mock_runner.run.side_effect = KeyError("my-device")
    response = client.get("/devices/my-device")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Item not found"}


def test_create_task(mock_runner: Mock, client: TestClient) -> None:
    task = Task(name="count", params={"detectors": ["x"]})
    task_id = str(uuid.uuid4())

    mock_runner.run.side_effect = [task_id]

    response = client.post("/tasks", json=task.model_dump())

    mock_runner.run.assert_called_with(submit_task, task)
    assert response.json() == {"task_id": task_id}


def test_create_task_validation_error(mock_runner: Mock, client: TestClient) -> None:
    mock_runner.run.side_effect = [
        ValidationError.from_exception_data(
            title="ValueError",
            line_errors=[
                InitErrorDetails(
                    type="missing", loc=("id",), msg="value is required for Identifier"
                )  # type: ignore
            ],
        ),
    ]

    response = client.post("/tasks", json={"name": "my-plan"})
    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "input": None,
                "loc": ["body", "params", "id"],
                "msg": "Field required",
                "type": "missing",
            }
        ]
    }


def test_put_plan_begins_task(client: TestClient) -> None:
    task_id = "04cd9aa6-b902-414b-ae4b-49ea4200e957"

    resp = client.put("/worker/task", json={"task_id": task_id})

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {"task_id": task_id}


def test_put_plan_fails_if_not_idle(mock_runner: Mock, client: TestClient) -> None:
    task_id_current = "260f7de3-b608-4cdc-a66c-257e95809792"
    task_id_new = "07e98d68-21b5-4ad7-ac34-08b2cb992d42"

    # Set to non idle
    mock_runner.run.return_value = TrackableTask(
        task=None, task_id=task_id_current, is_complete=False
    )

    resp = client.put("/worker/task", json={"task_id": task_id_new})

    assert resp.status_code == status.HTTP_409_CONFLICT
    assert resp.json() == {"detail": "Worker already active"}


def test_get_tasks(mock_runner: Mock, client: TestClient) -> None:
    tasks = [
        TrackableTask(task_id="0", task=Task(name="sleep", params={"time": 0.0})),
        TrackableTask(
            task_id="1",
            task=Task(name="first_task"),
            is_complete=False,
            is_pending=True,
        ),
    ]

    mock_runner.run.return_value = tasks

    response = client.get("/tasks")
    assert response.status_code == status.HTTP_200_OK

    assert response.json() == {
        "tasks": [
            {
                "errors": [],
                "is_complete": False,
                "is_pending": True,
                "request_id": None,
                "task": {"name": "sleep", "params": {"time": 0.0}},
                "task_id": "0",
            },
            {
                "errors": [],
                "is_complete": False,
                "is_pending": True,
                "request_id": None,
                "task": {"name": "first_task", "params": {}},
                "task_id": "1",
            },
        ]
    }


def test_get_tasks_by_status(mock_runner: Mock, client: TestClient) -> None:
    tasks = [
        TrackableTask(
            task_id="3",
            task=Task(name="third_task"),
            is_complete=True,
            is_pending=False,
        ),
    ]

    mock_runner.run.return_value = tasks

    response = client.get("/tasks", params={"task_status": "PENDING"})
    assert response.json() == {
        "tasks": [
            {
                "errors": [],
                "is_complete": True,
                "is_pending": False,
                "request_id": None,
                "task": {"name": "third_task", "params": {}},
                "task_id": "3",
            }
        ]
    }


def test_get_tasks_by_status_invalid(client: TestClient) -> None:
    response = client.get("/tasks", params={"task_status": "AN_INVALID_STATUS"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_delete_submitted_task(mock_runner: Mock, client: TestClient) -> None:
    task_id = str(uuid.uuid4())
    mock_runner.run.return_value = task_id
    response = client.delete(f"/tasks/{task_id}")
    assert response.json() == {"task_id": f"{task_id}"}


def test_set_active_task(client: TestClient) -> None:
    task_id = str(uuid.uuid4())
    task = WorkerTask(task_id=task_id)

    response = client.put("/worker/task", json=task.model_dump())

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"task_id": f"{task_id}"}


def test_set_active_task_active_task_complete(
    mock_runner: Mock, client: TestClient
) -> None:
    task_id = str(uuid.uuid4())
    task = WorkerTask(task_id=task_id)

    mock_runner.run.return_value = TrackableTask(
        task_id="1",
        task=Task(name="a_completed_task"),
        is_complete=True,
        is_pending=False,
    )

    response = client.put("/worker/task", json=task.model_dump())

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"task_id": f"{task_id}"}


def test_set_active_task_worker_already_running(
    mock_runner: Mock, client: TestClient
) -> None:
    task_id = str(uuid.uuid4())
    task = WorkerTask(task_id=task_id)

    mock_runner.run.return_value = TrackableTask(
        task_id="1",
        task=Task(name="a_running_task"),
        is_complete=False,
        is_pending=False,
    )

    response = client.put("/worker/task", json=task.model_dump())

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"detail": "Worker already active"}


def test_get_task(mock_runner: Mock, client: TestClient):
    task_id = str(uuid.uuid4())
    task = TrackableTask(
        task_id=task_id,
        task=Task(name="third_task"),
    )

    mock_runner.run.return_value = task

    response = client.get(f"/tasks/{task_id}")
    assert response.json() == {
        "errors": [],
        "is_complete": False,
        "is_pending": True,
        "request_id": None,
        "task": {"name": "third_task", "params": {}},
        "task_id": f"{task_id}",
    }


def test_get_all_tasks(mock_runner: Mock, client: TestClient):
    task_id = str(uuid.uuid4())
    tasks = [
        TrackableTask(
            task_id=task_id,
            task=Task(name="third_task"),
        )
    ]

    mock_runner.run.return_value = tasks
    response = client.get("/tasks")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "tasks": [
            {
                "task_id": task_id,
                "task": {"name": "third_task", "params": {}},
                "is_complete": False,
                "is_pending": True,
                "request_id": None,
                "errors": [],
            }
        ]
    }


def test_get_task_error(mock_runner: Mock, client: TestClient):
    task_id = 567
    mock_runner.run.return_value = None

    response = client.get(f"/tasks/{task_id}")
    assert response.json() == {"detail": "Item not found"}


def test_get_active_task(mock_runner: Mock, client: TestClient):
    task_id = str(uuid.uuid4())
    task = TrackableTask(
        task_id=task_id,
        task=Task(name="third_task"),
    )
    mock_runner.run.return_value = task

    response = client.get("/worker/task")

    assert response.json() == {"task_id": f"{task_id}"}


def test_get_active_task_none(mock_runner: Mock, client: TestClient):
    mock_runner.run.return_value = None

    response = client.get("/worker/task")

    assert response.json() == {"task_id": None}


def test_get_state(mock_runner: Mock, client: TestClient):
    state = WorkerState.SUSPENDING
    mock_runner.run.return_value = state

    response = client.get("/worker/state")
    assert response.json() == state


def test_set_state_running_to_paused(mock_runner: Mock, client: TestClient):
    current_state = WorkerState.RUNNING
    final_state = WorkerState.PAUSED
    mock_runner.run.side_effect = [current_state, None, final_state]

    response = client.put(
        "/worker/state", json=StateChangeRequest(new_state=final_state).model_dump()
    )

    mock_runner.run.assert_any_call(pause_worker, False)
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json() == final_state


def test_set_state_paused_to_running(mock_runner: Mock, client: TestClient):
    current_state = WorkerState.PAUSED
    final_state = WorkerState.RUNNING
    mock_runner.run.side_effect = [current_state, None, final_state]

    response = client.put(
        "/worker/state", json=StateChangeRequest(new_state=final_state).model_dump()
    )

    mock_runner.run.assert_any_call(resume_worker)
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json() == final_state


def test_set_state_running_to_aborting(mock_runner: Mock, client: TestClient):
    current_state = WorkerState.RUNNING
    final_state = WorkerState.ABORTING
    mock_runner.run.side_effect = [current_state, None, final_state]

    response = client.put(
        "/worker/state", json=StateChangeRequest(new_state=final_state).model_dump()
    )

    mock_runner.run.assert_any_call(cancel_active_task, True, None)
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json() == final_state


def test_set_state_running_to_stopping_including_reason(
    mock_runner: Mock, client: TestClient
):
    current_state = WorkerState.RUNNING
    final_state = WorkerState.STOPPING
    reason = "blueapi is being stopped"
    mock_runner.run.side_effect = [current_state, None, final_state]

    response = client.put(
        "/worker/state",
        json=StateChangeRequest(new_state=final_state, reason=reason).model_dump(),
    )

    mock_runner.run.assert_any_call(cancel_active_task, False, reason)
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json() == final_state


def test_set_state_transition_error(mock_runner: Mock, client: TestClient):
    current_state = WorkerState.RUNNING
    final_state = WorkerState.STOPPING

    mock_runner.run.side_effect = [current_state, TransitionError(), final_state]

    response = client.put(
        "/worker/state",
        json=StateChangeRequest(new_state=final_state).model_dump(),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == final_state


def test_set_state_invalid_transition(mock_runner: Mock, client: TestClient):
    current_state = WorkerState.STOPPING
    requested_state = WorkerState.PAUSED
    final_state = WorkerState.STOPPING

    mock_runner.run.side_effect = [current_state, final_state]

    response = client.put(
        "/worker/state",
        json=StateChangeRequest(new_state=requested_state).model_dump(),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == final_state


def test_get_environment_idle(mock_runner: Mock, client: TestClient) -> None:
    environment_id = uuid.uuid4()
    mock_runner.state = EnvironmentResponse(
        environment_id=environment_id,
        initialized=True,
        error_message=None,
    )

    assert client.get("/environment").json() == {
        "environment_id": str(environment_id),
        "initialized": True,
        "error_message": None,
    }


def test_delete_environment(mock_runner: Mock, client: TestClient) -> None:
    environment_id = uuid.uuid4()
    mock_runner.state = EnvironmentResponse(
        environment_id=environment_id,
        initialized=True,
        error_message=None,
    )
    response = client.delete("/environment")
    assert response.status_code is status.HTTP_200_OK
    assert response.json() == {
        "environment_id": str(environment_id),
        "initialized": False,
        "error_message": None,
    }


@patch("blueapi.service.runner.Pool")
def test_subprocess_enabled_by_default(mp_pool_mock: MagicMock):
    """Ensure that in the default rest app a subprocess runner is used"""
    main.setup_runner()
    mp_pool_mock.assert_called_once()
    main.teardown_runner()


def test_get_without_authentication(mock_runner: Mock, client: TestClient) -> None:
    mock_runner.run.side_effect = jwt.PyJWTError
    response = client.get("/devices/my-device")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Not authenticated"}


def test_oidc_config_not_found_when_auth_is_disabled(
    mock_runner: Mock, client: TestClient
):
    mock_runner.run.return_value = None
    response = client.get("/config/oidc")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.text == ""


def test_get_oidc_config(
    mock_runner: Mock,
    oidc_config: OIDCConfig,
    mock_authn_server,
    client_with_auth: TestClient,
):
    mock_runner.run.return_value = oidc_config
    response = client_with_auth.get("/config/oidc")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == oidc_config.model_dump()


def test_get_python_environment(mock_runner: Mock, client: TestClient):
    packages = PythonEnvironmentResponse(
        installed_packages=[
            PackageInfo(
                name="pydantic",
                version="2.10.6",
                source=SourceInfo.PYPI,
                is_dirty=False,
                location="/venv/site-packages/pydantic",
            )
        ]
    )
    mock_runner.run.return_value = packages
    response = client.get("/python_environment")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == packages.model_dump()


def test_health_probe(client: TestClient):
    response = client.get("/healthz")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}

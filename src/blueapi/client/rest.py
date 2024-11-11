from collections.abc import Callable, Mapping
from typing import Any, Literal, TypeVar

import jwt
import requests
from observability_utils.tracing import (
    get_context_propagator,
    get_tracer,
    start_as_current_span,
)
from pydantic import TypeAdapter

from blueapi.config import RestConfig
from blueapi.service.authentication import SessionManager
from blueapi.service.model import (
    DeviceModel,
    DeviceResponse,
    EnvironmentResponse,
    PlanModel,
    PlanResponse,
    TaskResponse,
    TasksListResponse,
    WorkerTask,
)
from blueapi.worker import Task, TrackableTask, WorkerState

T = TypeVar("T")

TRACER = get_tracer("rest")


class BlueskyRemoteControlError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def _exception(response: requests.Response) -> Exception | None:
    code = response.status_code
    if code < 400:
        return None
    elif code == 404:
        return KeyError(str(response.json()))
    else:
        return BlueskyRemoteControlError(str(response))


class BlueapiRestClient:
    _config: RestConfig

    def __init__(
        self,
        config: RestConfig | None = None,
        session_manager: SessionManager | None = None,
    ) -> None:
        self._config = config or RestConfig()
        self._session_manager = session_manager

    def get_plans(self) -> PlanResponse:
        return self._request_and_deserialize("/plans", PlanResponse)

    def get_plan(self, name: str) -> PlanModel:
        return self._request_and_deserialize(f"/plans/{name}", PlanModel)

    def get_devices(self) -> DeviceResponse:
        return self._request_and_deserialize("/devices", DeviceResponse)

    def get_device(self, name: str) -> DeviceModel:
        return self._request_and_deserialize(f"/devices/{name}", DeviceModel)

    def get_state(self) -> WorkerState:
        return self._request_and_deserialize("/worker/state", WorkerState)

    def set_state(
        self,
        state: Literal[WorkerState.RUNNING, WorkerState.PAUSED],
        defer: bool | None = False,
    ):
        return self._request_and_deserialize(
            "/worker/state",
            target_type=WorkerState,
            method="PUT",
            data={"new_state": state, "defer": defer},
        )

    def get_task(self, task_id: str) -> TrackableTask[Task]:
        return self._request_and_deserialize(f"/tasks/{task_id}", TrackableTask[Task])

    def get_all_tasks(self) -> TasksListResponse:
        return self._request_and_deserialize("/tasks", TasksListResponse)

    def get_active_task(self) -> WorkerTask:
        return self._request_and_deserialize("/worker/task", WorkerTask)

    def create_task(self, task: Task) -> TaskResponse:
        return self._request_and_deserialize(
            "/tasks",
            TaskResponse,
            method="POST",
            data=task.model_dump(),
        )

    def clear_task(self, task_id: str) -> TaskResponse:
        return self._request_and_deserialize(
            f"/tasks/{task_id}", TaskResponse, method="DELETE"
        )

    def update_worker_task(self, task: WorkerTask) -> WorkerTask:
        return self._request_and_deserialize(
            "/worker/task",
            WorkerTask,
            method="PUT",
            data=task.model_dump(),
        )

    def cancel_current_task(
        self,
        state: Literal[WorkerState.ABORTING, WorkerState.STOPPING],
        reason: str | None = None,
    ):
        return self._request_and_deserialize(
            "/worker/state",
            target_type=WorkerState,
            method="PUT",
            data={"new_state": state, "reason": reason},
        )

    def get_environment(self) -> EnvironmentResponse:
        return self._request_and_deserialize("/environment", EnvironmentResponse)

    def delete_environment(self) -> EnvironmentResponse:
        return self._request_and_deserialize(
            "/environment", EnvironmentResponse, method="DELETE"
        )

    @start_as_current_span(TRACER, "method", "data", "suffix")
    def _request_and_deserialize(
        self,
        suffix: str,
        target_type: type[T],
        data: Mapping[str, Any] | None = None,
        method="GET",
        get_exception: Callable[[requests.Response], Exception | None] = _exception,
    ) -> T:
        url = self._url(suffix)
        # Get the trace context to propagate to the REST API
        carr = get_context_propagator()
        if self._session_manager:
            # Attach authentication information if present
            token = self._session_manager.get_token()
            try:
                # Check token is not expired
                self._session_manager.decode_token(token)
            except jwt.ExpiredSignatureError:
                token = self._session_manager.refresh_auth_token()
            carr["Authorization"] = f"Bearer {token['access_token']}"

        if data:
            response = requests.request(method, url, json=data, headers=carr)
        else:
            response = requests.request(method, url, headers=carr)
        exception = get_exception(response)
        if exception is not None:
            raise exception
        deserialized = TypeAdapter(target_type).validate_python(response.json())
        return deserialized

    def _url(self, suffix: str) -> str:
        base_url = f"{self._config.protocol}://{self._config.host}:{self._config.port}"
        return f"{base_url}{suffix}"

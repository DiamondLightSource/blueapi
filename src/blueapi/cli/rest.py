from collections.abc import Callable, Mapping
from typing import Any, Literal, TypeVar

import requests
from pydantic import parse_obj_as

from blueapi.config import RestConfig
from blueapi.service.model import (
    DeviceModel,
    DeviceResponse,
    PlanModel,
    PlanResponse,
    TaskResponse,
    WorkerTask,
)
from blueapi.worker import Task, TrackableTask, WorkerState

from .event_bus_client import BlueskyRemoteError

T = TypeVar("T")


def _is_exception(response: requests.Response) -> bool:
    return response.status_code >= 400


class BlueapiRestClient:
    _config: RestConfig

    def __init__(self, config: RestConfig | None = None) -> None:
        self._config = config or RestConfig()

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

    def get_active_task(self) -> WorkerTask:
        return self._request_and_deserialize("/worker/task", WorkerTask)

    def create_task(self, task: Task) -> TaskResponse:
        return self._request_and_deserialize(
            "/tasks",
            TaskResponse,
            method="POST",
            data=task.dict(),
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
            data=task.dict(),
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

    def _request_and_deserialize(
        self,
        suffix: str,
        target_type: type[T],
        data: Mapping[str, Any] | None = None,
        method="GET",
        raise_if: Callable[[requests.Response], bool] = _is_exception,
    ) -> T:
        url = self._url(suffix)
        response = requests.request(method, url, json=data)
        if raise_if(response):
            raise BlueskyRemoteError(str(response))
        deserialized = parse_obj_as(target_type, response.json())
        return deserialized

    def _url(self, suffix: str) -> str:
        base_url = f"{self._config.protocol}://{self._config.host}:{self._config.port}"
        return f"{base_url}{suffix}"

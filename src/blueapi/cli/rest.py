from typing import Any, Mapping, Optional, Type, TypeVar

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
from blueapi.worker import RunPlan, TrackableTask, WorkerState

from .amq import BlueskyRemoteError

T = TypeVar("T")


class BlueapiRestClient:
    _config: RestConfig

    def __init__(self, config: Optional[RestConfig] = None) -> None:
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

    def get_task(self, task_id: str) -> TrackableTask[RunPlan]:
        return self._request_and_deserialize(
            f"/tasks/{task_id}", TrackableTask[RunPlan]
        )

    def get_active_task(self) -> WorkerTask:
        return self._request_and_deserialize("/worker/task", WorkerTask)

    def create_task(self, task: RunPlan) -> TaskResponse:
        return self._request_and_deserialize(
            "/tasks",
            TaskResponse,
            method="POST",
            data=task.dict(),
        )

    def update_worker_task(self, task: WorkerTask) -> WorkerTask:
        return self._request_and_deserialize(
            "/worker/task",
            WorkerTask,
            method="PUT",
            data=task.dict(),
        )

    def _request_and_deserialize(
        self,
        suffix: str,
        target_type: Type[T],
        data: Optional[Mapping[str, Any]] = None,
        method="GET",
    ) -> T:
        url = self._url(suffix)
        response = requests.request(method, url, json=data)
        if response.status_code >= 400:
            raise BlueskyRemoteError(str(response))
        deserialized = parse_obj_as(target_type, response.json())
        return deserialized

    def _url(self, suffix: str) -> str:
        base_url = f"{self._config.protocol}://{self._config.host}:{self._config.port}"
        return f"{base_url}{suffix}"
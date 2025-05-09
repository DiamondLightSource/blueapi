from collections.abc import Callable, Mapping
from typing import Any, Literal, TypeVar

import requests
from fastapi import status
from observability_utils.tracing import (
    get_context_propagator,
    get_tracer,
    start_as_current_span,
)
from pydantic import BaseModel, TypeAdapter, ValidationError

from blueapi.config import RestConfig
from blueapi.service.authentication import JWTAuth, SessionManager
from blueapi.service.model import (
    DeviceModel,
    DeviceResponse,
    EnvironmentResponse,
    OIDCConfig,
    PlanModel,
    PlanResponse,
    PythonEnvironmentResponse,
    SourceInfo,
    TaskResponse,
    TasksListResponse,
    WorkerTask,
)
from blueapi.worker import Task, TrackableTask, WorkerState

T = TypeVar("T")

TRACER = get_tracer("rest")


class UnauthorisedAccess(Exception):
    pass


class BlueskyRemoteControlError(Exception):
    pass


class BlueskyRequestError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message, code)


class NoContent(Exception):
    """Request returned 204 (No Content): handle if None is allowed"""

    def __init__(self, target_type: type) -> None:
        super().__init__(target_type)


class ParameterError(BaseModel):
    loc: list[str | int]
    msg: str
    type: str
    input: Any

    def field(self):
        return ".".join(str(p) for p in self.loc[2:] or self.loc)

    def __str__(self) -> str:
        match self.type:
            case "missing":
                return f"Missing value for {self.field()!r}"
            case "extra_forbidden":
                return f"Unexpected field {self.field()!r}"
            case _:
                return (
                    f"Invalid value {self.input!r} for field {self.field()}: {self.msg}"
                )


class InvalidParameters(Exception):
    def __init__(self, errors: list[ParameterError]):
        self.errors = errors

    def message(self):
        msg = "Incorrect parameters supplied"
        if self.errors:
            msg += "\n    " + "\n    ".join(str(e) for e in self.errors)
        return msg

    @classmethod
    def from_validation_error(cls, ve: ValidationError):
        return cls(
            [
                ParameterError(
                    loc=list(e["loc"]), msg=e["msg"], type=e["type"], input=e["input"]
                )
                for e in ve.errors()
            ]
        )


class UnknownPlan(Exception):
    pass


def _exception(response: requests.Response) -> Exception | None:
    code = response.status_code
    if code < 400:
        return None
    elif code == 404:
        return KeyError(str(response.json()))
    else:
        return BlueskyRemoteControlError(code, str(response))


def _create_task_exceptions(response: requests.Response) -> Exception | None:
    code = response.status_code
    if code < 400:
        return None
    elif code == 401 or code == 403:
        return UnauthorisedAccess()
    elif code == 404:
        return UnknownPlan()
    elif code == 422:
        try:
            content = response.json()
            return InvalidParameters(
                TypeAdapter(list[ParameterError]).validate_python(
                    content.get("detail", [])
                )
            )
        except Exception:
            # If the error can't be parsed into something sensible, return the
            # raw text in a generic exception so at least it gets reported
            return BlueskyRequestError(code, response.text)
    else:
        return BlueskyRequestError(code, response.text)


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
            get_exception=_create_task_exceptions,
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

    def get_oidc_config(self) -> OIDCConfig | None:
        try:
            return self._request_and_deserialize("/config/oidc", OIDCConfig)
        except NoContent:
            # Server is not using authentication
            return None

    def get_python_environment(
        self, name: str | None = None, source: SourceInfo | None = None
    ) -> PythonEnvironmentResponse:
        return self._request_and_deserialize(
            "/python_environment",
            PythonEnvironmentResponse,
            params={"name": name, "source": source},
        )

    @start_as_current_span(TRACER, "method", "data", "suffix")
    def _request_and_deserialize(
        self,
        suffix: str,
        target_type: type[T],
        data: Mapping[str, Any] | None = None,
        method="GET",
        get_exception: Callable[[requests.Response], Exception | None] = _exception,
        params: Mapping[str, Any] | None = None,
    ) -> T:
        url = self._url(suffix)
        # Get the trace context to propagate to the REST API
        carr = get_context_propagator()
        response = requests.request(
            method,
            url,
            json=data,
            params=params,
            headers=carr,
            auth=JWTAuth(self._session_manager),
        )
        exception = get_exception(response)
        if exception is not None:
            raise exception
        if response.status_code == status.HTTP_204_NO_CONTENT:
            raise NoContent(target_type)
        deserialized = TypeAdapter(target_type).validate_python(response.json())
        return deserialized

    def _url(self, suffix: str) -> str:
        base_url = f"{self._config.protocol}://{self._config.host}:{self._config.port}"
        return f"{base_url}{suffix}"

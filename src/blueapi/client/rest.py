import json
import logging
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Literal, TypeVar

import requests
from fastapi import status
from observability_utils.tracing import (
    get_context_propagator,
    get_tracer,
    start_as_current_span,
)
from pydantic import BaseModel, TypeAdapter, ValidationError, WebsocketUrl
from pydantic_core import PydanticSerializationError
from websockets.exceptions import InvalidStatus
from websockets.sync.client import connect

from blueapi import __version__
from blueapi.client import client
from blueapi.config import RestConfig
from blueapi.core.bluesky_types import DataEvent
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
    TaskRequest,
    TaskResponse,
    TasksListResponse,
    WorkerTask,
)
from blueapi.service.protocol import (
    ControlResponse,
    InvalidArgs,
    PlanNotFound,
    Submit,
    Update,
)
from blueapi.worker import TrackableTask, WorkerState
from blueapi.worker.event import ProgressEvent, WorkerEvent

T = TypeVar("T")

TRACER = get_tracer("rest")

LOGGER = logging.getLogger(__name__)

USER_AGENT = f"blueapi cli {__version__}"


class BlueskyRequestError(Exception):
    """An error response from the blueapi server."""

    def __init__(self, code: int | None = None, message: str = "") -> None:
        super().__init__(code, message)


class UnauthorisedAccessError(BlueskyRequestError):
    """Request was rejected due to missing or invalid credentials (401/403)."""

    pass


class NotFoundError(BlueskyRequestError):
    """Requested something that couldn't be found (404)."""

    pass


class UnknownPlanError(BlueskyRequestError):
    """Plan '{name}' was not recognised"""

    pass


class BlueskyRemoteControlError(Exception):
    """Unexpected or failed response from the blueapi server."""

    pass


class NonJsonResponseError(Exception):
    """Server returned a response that could not be parsed as JSON."""

    pass


class NoContentError(Exception):
    """Request returned 204 (No Content): handle if None is allowed"""

    def __init__(self, target_type: type) -> None:
        super().__init__(target_type)


class ParameterError(BaseModel):
    loc: list[str | int]
    msg: str | None
    type: str | None
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


class InvalidParametersError(Exception):
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


def _exception(response: requests.Response) -> Exception | None:
    code = response.status_code
    if code < 400:
        return None
    elif code in (401, 403):
        return UnauthorisedAccessError(code, response.text)
    elif code == 404:
        return NotFoundError(code, response.text)
    else:
        try:
            body = _response_json(response)
            message = (
                body.get("detail", response.text)
                if isinstance(body, dict)
                else response.text
            )
        except NonJsonResponseError:
            message = response.text
        return BlueskyRemoteControlError(code, message)


def _create_task_exceptions(response: requests.Response) -> Exception | None:
    code = response.status_code
    if code < 400:
        return None
    elif code == 401 or code == 403:
        return UnauthorisedAccessError(code, response.text)
    elif code == 404:
        return UnknownPlanError(code, response.text)
    elif code == 422:
        try:
            content = _response_json(response)
            return InvalidParametersError(
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


def _response_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except json.decoder.JSONDecodeError as exc:
        LOGGER.debug(
            f"Invalid json response from <{response.request.url}>: <{response.content}>"
        )
        raise NonJsonResponseError(
            "Response does not contain a valid JSON object"
        ) from exc


class BlueapiRestClient:
    _config: RestConfig
    _session_manager: SessionManager | None
    _pool: requests.Session

    def __init__(
        self,
        config: RestConfig | None = None,
        session_manager: SessionManager | None = None,
    ) -> None:
        self._config = config or RestConfig()
        self._session_manager = session_manager
        self._pool = requests.Session()

    def get_plans(self) -> PlanResponse:
        return self._request_and_deserialize("/plans", PlanResponse)

    def get_plan(self, name: str) -> PlanModel:
        try:
            return self._request_and_deserialize(f"/plans/{name}", PlanModel)
        except NotFoundError as e:
            raise UnknownPlanError(404, f"Plan '{name}' not found") from e

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

    def get_task(self, task_id: str) -> TrackableTask:
        return self._request_and_deserialize(f"/tasks/{task_id}", TrackableTask)

    def get_all_tasks(self) -> TasksListResponse:
        return self._request_and_deserialize("/tasks", TasksListResponse)

    def get_active_task(self) -> WorkerTask:
        return self._request_and_deserialize("/worker/task", WorkerTask)

    def create_task(self, task: TaskRequest) -> TaskResponse:
        return self._request_and_deserialize(
            "/tasks",
            TaskResponse,
            method="POST",
            get_exception=_create_task_exceptions,
            data=task.model_dump(mode="json", fallback=_task_model_fallback),
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
        except NoContentError:
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
        url = self._config.url.unicode_string().removesuffix("/") + suffix
        # Get the trace context to propagate to the REST API
        headers = get_context_propagator()
        headers["User-Agent"] = USER_AGENT
        try:
            response = self._pool.request(
                method,
                url,
                json=data,
                params=params,
                headers=headers,
                auth=JWTAuth(self._session_manager),
            )
        except requests.exceptions.ConnectionError as ce:
            raise ServiceUnavailableError() from ce
        exception = get_exception(response)
        if exception is not None:
            raise exception
        if response.status_code == status.HTTP_204_NO_CONTENT:
            raise NoContentError(target_type)
        if (server_version := response.headers.get("x-blueapi-version")) is not None:
            from packaging.version import Version

            if (server_version := Version(server_version).base_version) != (
                client_version := Version(__version__).base_version
            ):
                LOGGER.warning(
                    f"Version mismatch: Blueapi server version is {server_version} "
                    f"but client version is {client_version}. "
                    f"Some features may not work as expected."
                )
        deserialized = TypeAdapter(target_type).validate_python(
            _response_json(response)
        )
        return deserialized

    def run_blocking(
        self, req: TaskRequest
    ) -> Iterable[DataEvent | WorkerEvent | ProgressEvent]:
        url = self._ws_address().unicode_string().removesuffix("/") + "/api/v2/run_plan"
        headers = get_context_propagator()
        if self._session_manager:
            auth = self._session_manager.get_valid_access_token()
            headers["Authorization"] = f"Bearer {auth}"
        try:
            with connect(
                url,
                additional_headers=headers,
                user_agent_header=USER_AGENT,
            ) as ws:
                ws.send(Submit(task=req).model_dump_json())
                for message in ws:
                    event = ControlResponse.validate_json(message)
                    match event:
                        case Update(data=data):
                            yield data
                        case InvalidArgs(errors=errors):
                            raise InvalidParametersError(
                                [
                                    ParameterError(
                                        loc=e.loc, msg=e.msg, type=e.type, input=e.input
                                    )
                                    for e in errors
                                ]
                            )
                        case PlanNotFound(plan_name=name):
                            raise UnknownPlanError(name)
        except InvalidStatus as istat:
            match istat.response.status_code:
                case 401 | 403:
                    raise UnauthorisedAccessError() from None
            print(vars(istat))
            return

    def _ws_address(self) -> WebsocketUrl:
        api = self._config.url
        if api.host is None:
            raise ValueError("No host configured")
        scheme = "ws" if api.scheme == "http" else "wss"
        return WebsocketUrl.build(
            scheme=scheme, host=api.host, port=api.port, path=api.path
        )


# https://github.com/DiamondLightSource/blueapi/issues/1256 - remove before 2.0
def __getattr__(name: str):
    import warnings

    renames = {
        "InvalidParameters": InvalidParametersError,
        "NoContent": NoContentError,
        "UnauthorisedAccess": UnauthorisedAccessError,
        "UnknownPlan": UnknownPlanError,
    }
    rename = renames.get(name)
    if rename is not None:
        warnings.warn(
            DeprecationWarning(
                f"{name!r} is deprecated, use {rename.__name__!r} instead"
            ),
            stacklevel=2,
        )
        return rename
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class ServiceUnavailableError(Exception):
    pass


def _task_model_fallback(obj: Any) -> Any:
    """Fallback method for serializing TaskRequests"""
    if isinstance(obj, client.DeviceRef):
        return obj.name
    raise PydanticSerializationError(f"Object of type {type(obj)} not serializable")

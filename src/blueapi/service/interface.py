import threading
import time
from collections.abc import Mapping
from enum import Enum
from functools import cache
from typing import Any, cast

import httpx
from bluesky.callbacks.tiled_writer import TiledWriter
from bluesky_stomp.messaging import StompClient
from bluesky_stomp.models import Broker, DestinationBase, MessageTopic
from pydantic import BaseModel, computed_field
from tiled.client import from_uri

from blueapi.cli.scratch import get_python_environment
from blueapi.config import ApplicationConfig, OIDCConfig, StompConfig, TiledConfig
from blueapi.core.context import BlueskyContext
from blueapi.core.event import EventStream
from blueapi.log import set_up_logging
from blueapi.service.constants import AUTHORIZAITON_HEADER
from blueapi.service.model import (
    DeviceModel,
    PlanModel,
    PythonEnvironmentResponse,
    SourceInfo,
    TaskRequest,
    WorkerTask,
)
from blueapi.utils.serialization import access_blob
from blueapi.worker.event import TaskStatusEnum, WorkerEvent, WorkerState
from blueapi.worker.task import Task
from blueapi.worker.task_worker import TaskWorker, TrackableTask

"""This module provides interface between web application and underlying Bluesky
context and worker"""


_CONFIG: ApplicationConfig = ApplicationConfig()


def config() -> ApplicationConfig:
    return _CONFIG


def set_config(new_config: ApplicationConfig):
    global _CONFIG

    _CONFIG = new_config


@cache
def context() -> BlueskyContext:
    ctx = BlueskyContext(config())
    return ctx


@cache
def worker() -> TaskWorker:
    worker = TaskWorker(
        context(),
        broadcast_statuses=config().env.events.broadcast_status_events,
    )
    worker.start()
    return worker


@cache
def stomp_client() -> StompClient | None:
    stomp_config: StompConfig = config().stomp
    if stomp_config.enabled:
        assert stomp_config.url.host is not None, "Stomp URL missing host"
        assert stomp_config.url.port is not None, "Stomp URL missing port"
        client = StompClient.for_broker(
            broker=Broker(
                host=stomp_config.url.host,
                port=stomp_config.url.port,
                auth=stomp_config.auth,
            )
        )

        task_worker = worker()
        event_topic = MessageTopic(name="public.worker.event")

        _publish_event_streams(
            {
                task_worker.worker_events: event_topic,
                task_worker.progress_events: event_topic,
                task_worker.data_events: event_topic,
            }
        )
        client.connect()
        return client
    else:
        return None


def setup(config: ApplicationConfig) -> None:
    """Creates and starts a worker with supplied config"""
    set_config(config)
    set_up_logging(config.logging)

    # Eagerly initialize worker and messaging connection
    worker()
    stomp_client()


def teardown() -> None:
    worker().stop()
    if (stomp_client_ref := stomp_client()) is not None:
        stomp_client_ref.disconnect()
    context.cache_clear()
    worker.cache_clear()
    stomp_client.cache_clear()


def _publish_event_streams(
    streams_to_destinations: Mapping[EventStream, DestinationBase],
) -> None:
    for stream, destination in streams_to_destinations.items():
        _publish_event_stream(stream, destination)


def _publish_event_stream(stream: EventStream, destination: DestinationBase) -> None:
    def forward_message(event: Any, correlation_id: str | None) -> None:
        if (stomp_client_ref := stomp_client()) is not None:
            stomp_client_ref.send(
                destination, event, None, correlation_id=correlation_id
            )

    stream.subscribe(forward_message)


def get_plans() -> list[PlanModel]:
    """Get all available plans in the BlueskyContext"""
    return [PlanModel.from_plan(plan) for plan in context().plans.values()]


def get_plan(name: str) -> PlanModel:
    """Get plan by name from the BlueskyContext"""
    return PlanModel.from_plan(context().plans[name])


def get_devices() -> list[DeviceModel]:
    """Get all available devices in the BlueskyContext"""
    return [DeviceModel.from_device(device) for device in context().devices.values()]


def get_device(name: str) -> DeviceModel:
    """Retrieve device by name from the BlueskyContext"""
    return DeviceModel.from_device(context().devices[name])


def submit_task(task_request: TaskRequest) -> str:
    """Submit a task to be run on begin_task"""
    metadata: dict[str, Any] = {
        "instrument_session": task_request.instrument_session,
    }
    if context().tiled_conf is not None:
        md = config().env.metadata
        # We raise an InvalidConfigError on setting tiled_conf if this isn't set
        assert md
        metadata["tiled_access_tags"] = [
            access_blob(task_request.instrument_session, md.instrument)
        ]
    task = Task(
        name=task_request.name,
        params=task_request.params,
        metadata=metadata,
    )
    return worker().submit_task(task)


def clear_task(task_id: str) -> str:
    """Remove a task from the worker"""
    return worker().clear_task(task_id)


class TokenType(str, Enum):
    refresh_token = "refresh_token"
    access_token = "access_token"


class Token(BaseModel):
    token: str
    expires_at: float | None

    @computed_field
    @property
    def expired(self) -> bool:
        if self.expires_at is None:
            # Assume token is valid
            return False
        return time.time() > self.expires_at

    def _get_token_expires_at(
        self, token_dict: dict[str, Any], token_type: TokenType
    ) -> int | None:
        expires_at = None
        if token_type == TokenType.access_token:
            if "expires_at" in token_dict:
                expires_at = int(token_dict["expires_at"])
            elif "expires_in" in token_dict:
                expires_at = int(time.time()) + int(token_dict["expires_in"])
        elif token_type == TokenType.refresh_token:
            if "refresh_expires_at" in token_dict:
                expires_at = int(token_dict["refresh_expires_at"])
            elif "refresh_expires_in" in token_dict:
                expires_at = int(time.time()) + int(token_dict["refresh_expires_in"])
        return expires_at

    def __init__(self, token_dict: dict[str, Any], token_type: TokenType):
        token = token_dict.get(token_type)
        if token is None:
            raise ValueError(f"Not able to find {token_type} in response")
        super().__init__(
            token=token, expires_at=self._get_token_expires_at(token_dict, token_type)
        )

    def __str__(self) -> str:
        return str(self.token)


class TiledAuth(httpx.Auth):
    def __init__(self, tiled_config: TiledConfig, blueapi_jwt_token: str):
        self._tiled_config = tiled_config
        self._blueapi_jwt_token = blueapi_jwt_token
        self._sync_lock = threading.RLock()
        self._access_token: Token | None = None
        self._refresh_token: Token | None = None

    def exchange_access_token(self):
        request_data = {
            "client_id": self._tiled_config.token_exchange_client_id,
            "client_secret": self._tiled_config.token_exchange_secret,
            "subject_token": self._blueapi_jwt_token,
            "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "requested_token_type": "urn:ietf:params:oauth:token-type:refresh_token",
        }
        with self._sync_lock:
            response = httpx.post(
                self._tiled_config.token_url,
                data=request_data,
            )
            response.raise_for_status()
            self.sync_tokens(response.json())

    def refresh_token(self):
        if self._refresh_token is None:
            raise Exception("Cannot refresh tokens as no refresh token available")
        with self._sync_lock:
            response = httpx.post(
                self._tiled_config.token_url,
                data={
                    "client_id": self._tiled_config.token_exchange_client_id,
                    "client_secret": self._tiled_config.token_exchange_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            self.sync_tokens(response.json())

    def sync_tokens(self, response):
        self._access_token = Token(response, TokenType.access_token)
        self._refresh_token = Token(response, TokenType.refresh_token)

    def sync_auth_flow(self, request):
        response = None
        if self._access_token is not None and self._access_token.expired is not True:
            request.headers["Authorization"] = f"Bearer {self._access_token}"
            response = yield request
        elif self._access_token is None:
            self.exchange_access_token()
            request.headers["Authorization"] = f"Bearer {self._access_token}"
            response = yield request
        elif (
            cast(httpx.Response, response).status_code == httpx.codes.UNAUTHORIZED
            or self._access_token.expired
        ):
            self.refresh_token()
            request.headers["Authorization"] = f"Bearer {self._access_token}"
            response = yield request


def begin_task(
    task: WorkerTask, pass_through_headers: Mapping[str, str] | None = None
) -> WorkerTask:
    """Trigger a task. Will fail if the worker is busy"""

    active_worker = worker()
    active_context = context()
    if nt := active_context.numtracker:
        nt.set_headers(pass_through_headers or {})

    if tiled_config := active_context.tiled_conf:
        # Tiled queries the root node, so must create an authorized client
        blueapi_jwt_token = ""
        if pass_through_headers is None:
            raise ValueError(
                f"Tiled config is enabled but no {AUTHORIZAITON_HEADER} in request"
            )
        authorization_header_value = pass_through_headers.get(AUTHORIZAITON_HEADER)
        from fastapi.security.utils import get_authorization_scheme_param

        _, blueapi_jwt_token = get_authorization_scheme_param(
            authorization_header_value
        )

        if blueapi_jwt_token == "":
            raise KeyError("Tiled config is enabled but no Bearer Token in request")
        tiled_client = from_uri(
            str(tiled_config.url),
            auth=TiledAuth(
                tiled_config,
                blueapi_jwt_token=blueapi_jwt_token,
            ),
        )
        tiled_writer_token = active_context.run_engine.subscribe(
            TiledWriter(tiled_client, batch_size=1)
        )

        def remove_callback_when_task_finished(
            event: WorkerEvent, correlation_id: str | None
        ) -> None:
            if (
                event.task_status
                and event.task_status.task_id == task.task_id
                and event.task_status.task_complete
            ):
                active_context.run_engine.unsubscribe(tiled_writer_token)
                active_worker.worker_events.unsubscribe(remove_callback)

        remove_callback = active_worker.worker_events.subscribe(
            remove_callback_when_task_finished
        )

    if task.task_id is not None:
        active_worker.begin_task(task.task_id)
    return task


def get_tasks_by_status(status: TaskStatusEnum) -> list[TrackableTask]:
    """Retrieve a list of tasks based on their status."""
    return worker().get_tasks_by_status(status)


def get_active_task() -> TrackableTask | None:
    """Task the worker is currently running"""
    return worker().get_active_task()


def get_worker_state() -> WorkerState:
    """State of the worker"""
    return worker().state


def pause_worker(defer: bool | None) -> None:
    """Command the worker to pause"""
    worker().pause(defer or False)


def resume_worker() -> None:
    """Command the worker to resume"""
    worker().resume()


def cancel_active_task(failure: bool, reason: str | None) -> str:
    """Remove the currently active task from the worker if there is one
    Returns the task_id of the active task"""
    return worker().cancel_active_task(failure, reason)


def get_tasks() -> list[TrackableTask]:
    """Return a list of all tasks on the worker,
    any one of which can be triggered with begin_task"""
    return worker().get_tasks()


def get_task_by_id(task_id: str) -> TrackableTask | None:
    """Returns a task matching the task ID supplied,
    if the worker knows of it"""
    return worker().get_task_by_id(task_id)


def get_oidc_config() -> OIDCConfig | None:
    return config().oidc


def get_python_env(
    name: str | None = None, source: SourceInfo | None = None
) -> PythonEnvironmentResponse:
    """Retrieve information about the Python environment"""
    scratch = config().scratch
    return get_python_environment(config=scratch, name=name, source=source)

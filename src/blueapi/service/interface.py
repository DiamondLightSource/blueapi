from collections.abc import Mapping
from functools import cache
from typing import Any

from bluesky_stomp.messaging import StompClient
from bluesky_stomp.models import Broker, DestinationBase, MessageTopic
from dodal.common.beamlines.beamline_utils import (
    get_path_provider,
    set_path_provider,
)

from blueapi.cli.scratch import get_python_environment
from blueapi.client.numtracker import NumtrackerClient
from blueapi.config import ApplicationConfig, OIDCConfig, StompConfig
from blueapi.core.context import BlueskyContext
from blueapi.core.event import EventStream
from blueapi.log import set_up_logging
from blueapi.service.model import (
    DeviceModel,
    PlanModel,
    PythonEnvironmentResponse,
    SourceInfo,
    WorkerTask,
)
from blueapi.utils.invalid_config_error import InvalidConfigError
from blueapi.utils.path_provider import StartDocumentPathProvider
from blueapi.worker.event import TaskStatusEnum, WorkerState
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
    ctx = BlueskyContext()
    ctx.with_config(config().env)
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
        client = StompClient.for_broker(
            broker=Broker(
                host=stomp_config.host,
                port=stomp_config.port,
                auth=stomp_config.auth,  # type: ignore
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


@cache
def numtracker_client() -> NumtrackerClient | None:
    conf = config()
    if conf.numtracker is not None:
        if conf.env.metadata is not None:
            return NumtrackerClient(url=conf.numtracker.url)
        else:
            raise InvalidConfigError(
                "Numtracker url has been configured, but there is no instrument or"
                " instrument_session in the environment metadata"
            )
    else:
        return None


def _update_scan_num(md: dict[str, Any]) -> int:
    numtracker = numtracker_client()
    if numtracker is not None:
        scan = numtracker.create_scan(md["instrument_session"], md["instrument"])
        md["instrument_session_directory"] = str(scan.scan.directory.path)
        return scan.scan.scan_number
    else:
        raise InvalidConfigError(
            "Blueapi was configured to talk to numtracker but numtracker is not"
            "configured, this should not happen, please contact the DAQ team"
        )


def setup(config: ApplicationConfig) -> None:
    """Creates and starts a worker with supplied config"""
    set_config(config)
    set_up_logging(config.logging)

    # Eagerly initialize worker and messaging connection
    worker()
    stomp_client()
    if numtracker_client() is not None:
        context().run_engine.scan_id_source = _update_scan_num
        _hook_run_engine_and_path_provider()


def _hook_run_engine_and_path_provider() -> None:
    try:
        path_provider = get_path_provider()
    except NameError:
        path_provider = None

    run_engine = context().run_engine

    if path_provider is None:
        path_provider = StartDocumentPathProvider()
        set_path_provider(path_provider)
        run_engine.subscribe(path_provider.update_run, "start")
    else:
        raise InvalidConfigError(
            "A StartDocumentPathProvider has not been configured for numtracker"
            f"because a different path provider was already set: {path_provider}"
        )


def teardown() -> None:
    worker().stop()
    if (stomp_client_ref := stomp_client()) is not None:
        stomp_client_ref.disconnect()
    context.cache_clear()
    worker.cache_clear()
    stomp_client.cache_clear()
    numtracker_client.cache_clear()


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


def submit_task(task: Task) -> str:
    """Submit a task to be run on begin_task"""
    return worker().submit_task(task)


def clear_task(task_id: str) -> str:
    """Remove a task from the worker"""
    return worker().clear_task(task_id)


def begin_task(
    task: WorkerTask, pass_through_headers: Mapping[str, str] | None = None
) -> WorkerTask:
    """Trigger a task. Will fail if the worker is busy"""
    if pass_through_headers:
        _try_configure_numtracker(pass_through_headers)

    if task.task_id is not None:
        worker().begin_task(task.task_id)
    return task


def _try_configure_numtracker(pass_through_headers: Mapping[str, str]) -> None:
    numtracker = numtracker_client()
    if numtracker is not None:
        numtracker.set_headers(pass_through_headers)


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

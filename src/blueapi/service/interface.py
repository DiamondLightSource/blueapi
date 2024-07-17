from collections.abc import Mapping
from typing import Any

from blueapi.config import ApplicationConfig
from blueapi.core.context import BlueskyContext
from blueapi.core.event import EventStream
from blueapi.messaging.base import MessagingTemplate
from blueapi.messaging.stomptemplate import StompMessagingTemplate
from blueapi.service.model import (
    DeviceModel,
    PlanModel,
    WorkerTask,
)
from blueapi.worker.event import TaskStatusEnum, WorkerState
from blueapi.worker.reworker import TaskWorker
from blueapi.worker.task import Task
from blueapi.worker.worker import TrackableTask, Worker

"""This module provides interface between web application and underlying Bluesky
context and worker"""


class InitialisationException(Exception):
    pass


class _Singleton:
    context: BlueskyContext
    worker: Worker
    messaging_template: MessagingTemplate | None = None
    initialized = False


def start_worker(
    config: ApplicationConfig,
    bluesky_context: BlueskyContext = None,
    worker: TaskWorker = None,
) -> None:
    """Creates and starts a worker with supplied config"""
    if _Singleton.initialized:
        raise InitialisationException(
            "Worker is already running. To reload call stop first"
        )
    _Singleton.context = bluesky_context
    if _Singleton.context is None:
        _Singleton.context = BlueskyContext()
        _Singleton.context.with_config(config.env)
    _Singleton.worker = worker
    if _Singleton.worker is None:
        _Singleton.worker = TaskWorker(
            _Singleton.context,
            broadcast_statuses=config.env.events.broadcast_status_events,
        )
    if config.stomp is not None:
        _Singleton.messaging_template = StompMessagingTemplate.autoconfigured(
            config.stomp
        )

    # Start worker and setup events
    _Singleton.worker.start()
    if _Singleton.messaging_template is not None:
        event_topic = _Singleton.messaging_template.destinations.topic(
            "public.worker.event"
        )

        _publish_event_streams(
            {
                _Singleton.worker.worker_events: event_topic,
                _Singleton.worker.progress_events: event_topic,
                _Singleton.worker.data_events: event_topic,
            }
        )
        _Singleton.messaging_template.connect()
    _Singleton.initialized = True


def _publish_event_streams(streams_to_destinations: Mapping[EventStream, str]) -> None:
    for stream, destination in streams_to_destinations.items():
        _publish_event_stream(stream, destination)


def _publish_event_stream(stream: EventStream, destination: str) -> None:
    def forward_message(event: Any, correlation_id: str | None) -> None:
        if _Singleton.messaging_template is not None:
            _Singleton.messaging_template.send(destination, event, None, correlation_id)

    stream.subscribe(forward_message)


def stop_worker() -> None:
    if not _Singleton.initialized:
        raise InitialisationException(
            "Cannot stop worker as it hasn't been started yet"
        )
    _Singleton.initialized = False
    _Singleton.worker.stop()
    if (
        _Singleton.messaging_template is not None
        and _Singleton.messaging_template.is_connected()
    ):
        _Singleton.messaging_template.disconnect()
    _Singleton.worker = None
    _Singleton.context = None
    _Singleton.messaging_template = None


def get_plans() -> list[PlanModel]:
    """Get all available plans in the BlueskyContext"""
    _ensure_worker_started()
    return [PlanModel.from_plan(plan) for plan in _Singleton.context.plans.values()]


def get_plan(name: str) -> PlanModel:
    """Get plan by name from the BlueskyContext"""
    _ensure_worker_started()
    return PlanModel.from_plan(_Singleton.context.plans[name])


def get_devices() -> list[DeviceModel]:
    """Get all available devices in the BlueskyContext"""
    _ensure_worker_started()
    return [
        DeviceModel.from_device(device)
        for device in _Singleton.context.devices.values()
    ]


def get_device(name: str) -> DeviceModel:
    """Retrieve device by name from the BlueskyContext"""
    _ensure_worker_started()
    return DeviceModel.from_device(_Singleton.context.devices[name])


def submit_task(task: Task) -> str:
    """Submit a task to be run on begin_task"""
    _ensure_worker_started()
    return _Singleton.worker.submit_task(task)


def clear_task(task_id: str) -> str:
    """Remove a task from the worker"""
    _ensure_worker_started()
    return _Singleton.worker.clear_task(task_id)


def begin_task(task: WorkerTask) -> WorkerTask:
    """Trigger a task. Will fail if the worker is busy"""
    _ensure_worker_started()
    if task.task_id is not None:
        _Singleton.worker.begin_task(task.task_id)
    return task


def get_tasks_by_status(status: TaskStatusEnum) -> list[TrackableTask]:
    """Retrieve a list of tasks based on their status."""
    _ensure_worker_started()
    return _Singleton.worker.get_tasks_by_status(status)


def get_active_task() -> TrackableTask | None:
    """Task the worker is currently running"""
    _ensure_worker_started()
    return _Singleton.worker.get_active_task()


def get_worker_state() -> WorkerState:
    """State of the worker"""
    _ensure_worker_started()
    return _Singleton.worker.state


def pause_worker(defer: bool | None) -> None:
    """Command the worker to pause"""
    _ensure_worker_started()
    _Singleton.worker.pause(defer)


def resume_worker() -> None:
    """Command the worker to resume"""
    _ensure_worker_started()
    _Singleton.worker.resume()


def cancel_active_task(failure: bool, reason: str | None) -> str:
    """Remove the currently active task from the worker if there is one
    Returns the task_id of the active task"""
    _ensure_worker_started()
    return _Singleton.worker.cancel_active_task(failure, reason)


def get_tasks() -> list[TrackableTask]:
    """Return a list of all tasks on the worker,
    any one of which can be triggered with begin_task"""
    _ensure_worker_started()
    return _Singleton.worker.get_tasks()


def get_task_by_id(task_id: str) -> TrackableTask | None:
    """Returns a task matching the task ID supplied,
    if the worker knows of it"""
    _ensure_worker_started()
    return _Singleton.worker.get_task_by_id(task_id)


def get_state() -> bool:
    """Initialization state"""
    return _Singleton.initialized


def _ensure_worker_started() -> None:
    if _Singleton.initialized:
        return
    raise InitialisationException("Worker must be stared before it is used")

import logging
from collections.abc import Mapping
from functools import cache
from typing import Any

from bluesky_stomp.messaging import StompClient
from bluesky_stomp.models import Broker, DestinationBase, MessageTopic

from blueapi.config import ApplicationConfig
from blueapi.core.context import BlueskyContext
from blueapi.core.event import EventStream
from blueapi.service.model import DeviceModel, PlanModel, WorkerTask
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
    stomp_config = config().stomp
    if stomp_config is not None:
        stomp_client = StompClient.for_broker(
            broker=Broker(
                host=stomp_config.host, port=stomp_config.port, auth=stomp_config.auth
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
        stomp_client.connect()
        return stomp_client
    else:
        return None


def setup(config: ApplicationConfig) -> None:
    """Creates and starts a worker with supplied config"""

    set_config(config)

    # Eagerly initialize worker and messaging connection

    logging.basicConfig(format="%(asctime)s - %(message)s", level=config.logging.level)
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


def submit_task(task: Task) -> str:
    """Submit a task to be run on begin_task"""
    return worker().submit_task(task)


def clear_task(task_id: str) -> str:
    """Remove a task from the worker"""
    return worker().clear_task(task_id)


def begin_task(task: WorkerTask) -> WorkerTask:
    """Trigger a task. Will fail if the worker is busy"""
    if task.task_id is not None:
        worker().begin_task(task.task_id)
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

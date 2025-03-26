import uuid
from collections.abc import Iterable
from enum import Enum
from typing import Any, get_args

from bluesky.protocols import HasName
from pydantic import Field

from blueapi.config import OIDCConfig
from blueapi.core import BLUESKY_PROTOCOLS, Device, Plan
from blueapi.utils import BlueapiBaseModel
from blueapi.worker import WorkerState
from blueapi.worker.task_worker import TaskWorker, TrackableTask

_UNKNOWN_NAME = "UNKNOWN"


class ProtocolInfo(BlueapiBaseModel):
    name: str
    types: list[str] = []

    def __str__(self):
        return f"{self.name}{self.types or ''}"


class DeviceModel(BlueapiBaseModel):
    """
    Representation of a device
    """

    name: str = Field(description="Name of the device")
    protocols: list[ProtocolInfo] = Field(
        description="Protocols that a device conforms to, indicating its capabilities"
    )

    @classmethod
    def from_device(cls, device: Device) -> "DeviceModel":
        name = device.name if isinstance(device, HasName) else _UNKNOWN_NAME
        return cls(name=name, protocols=list(_protocol_names(device)))


def generic_bounds(device, protocol) -> list[str]:
    for base in getattr(device, "__orig_bases__", ()):
        if getattr(base, "__name__", None) == protocol.__name__:
            return [arg.__name__ for arg in get_args(base)]
    return []


def _protocol_names(device: Device) -> Iterable[ProtocolInfo]:
    for protocol in BLUESKY_PROTOCOLS:
        if isinstance(device, protocol):
            yield ProtocolInfo(
                name=protocol.__name__, types=generic_bounds(device, protocol)
            )


class TasksListResponse(BlueapiBaseModel):
    """
    Diagnostic information on the tasks
    """

    tasks: list[TrackableTask] = Field(description="List of tasks")


class DeviceRequest(BlueapiBaseModel):
    """
    A query for devices
    """

    ...


class DeviceResponse(BlueapiBaseModel):
    """
    Response to a query for devices
    """

    devices: list[DeviceModel] = Field(description="Devices available to use in plans")


class PlanModel(BlueapiBaseModel):
    """
    Representation of a plan
    """

    name: str = Field(description="Name of the plan")
    description: str | None = Field(description="Docstring of the plan", default=None)
    parameter_schema: dict[str, Any] | None = Field(
        description="Schema of the plan's parameters",
        alias="schema",
        default_factory=dict,
    )

    @classmethod
    def from_plan(cls, plan: Plan) -> "PlanModel":
        return cls(
            name=plan.name,
            schema=plan.model.model_json_schema(),
            description=plan.description,
        )


class PlanRequest(BlueapiBaseModel):
    """
    A query for plans
    """

    ...


class PlanResponse(BlueapiBaseModel):
    """
    Response to a query for plans
    """

    plans: list[PlanModel] = Field(description="Plans available to use by a worker")


class TaskResponse(BlueapiBaseModel):
    """
    Acknowledgement that a task has started, includes its ID
    """

    task_id: str = Field(description="Unique identifier for the task")


class WorkerTask(BlueapiBaseModel):
    """
    Worker's active task ID, can be None
    """

    task_id: str | None = Field(
        description="The ID of the current task, None if the worker is idle"
    )

    @classmethod
    def of_worker(cls, worker: TaskWorker) -> "WorkerTask":
        active = worker.get_active_task()
        if active is not None:
            return WorkerTask(task_id=active.task_id)
        else:
            return WorkerTask(task_id=None)


class StateChangeRequest(BlueapiBaseModel):
    """
    Request to change the state of the worker.
    """

    new_state: WorkerState = Field()
    defer: bool = Field(
        description="Should worker defer Pausing until the next checkpoint",
        default=False,
    )
    reason: str | None = Field(
        description="The reason for the current run to be aborted",
        default=None,
    )


class EnvironmentResponse(BlueapiBaseModel):
    """
    State of internal environment.
    """

    environment_id: uuid.UUID = Field(
        description="Unique ID for the environment instance, can be used to "
        "differentiate between a new environment and old that has been torn down"
    )
    initialized: bool = Field(description="blueapi context initialized")
    error_message: str | None = Field(
        default=None,
        description="If present - error loading context",
        min_length=1,
    )


class SourceInfo(str, Enum):
    pypi = "pypi"
    scratch = "scratch"


class PackageInfo(BlueapiBaseModel):
    name: str = Field(description="Name of the package")
    version: str = Field(description="Version of the package")
    location: str = Field(description="Location of the package")
    is_dirty: bool = Field(description="Does the package have uncommitted changes")
    source: SourceInfo = Field(
        description="Source of the package", default=SourceInfo.pypi
    )


class ScratchResponse(BlueapiBaseModel):
    """
    State of the scratch area.
    """

    installed_packages: list[PackageInfo] = Field(
        description="List of installed packages", default_factory=list
    )
    enabled: bool = Field(description="Scratch area state", default=False)


class Cache(BlueapiBaseModel):
    """
    Represents the cached data required for managing authentication.
    """

    oidc_config: OIDCConfig
    access_token: str
    refresh_token: str
    id_token: str

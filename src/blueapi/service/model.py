import uuid
from collections.abc import Iterable
from enum import Enum
from typing import Annotated, Any

from bluesky.protocols import HasName
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from blueapi.config import OIDCConfig
from blueapi.core import BLUESKY_PROTOCOLS, Device, Plan
from blueapi.core.context import generic_bounds
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
        return cls(name=name, protocols=list(_protocol_info(device)))


def _protocol_info(device: Device) -> Iterable[ProtocolInfo]:
    for protocol in BLUESKY_PROTOCOLS:
        if isinstance(device, protocol):
            yield ProtocolInfo(
                name=protocol.__name__,
                types=[arg.__name__ for arg in generic_bounds(device, protocol)],
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
    description: str | SkipJsonSchema[None] = Field(
        description="Docstring of the plan", default=None
    )
    parameter_schema: dict[str, Any] | SkipJsonSchema[None] = Field(
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

    task_id: str | SkipJsonSchema[None] = Field(
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
    reason: str | SkipJsonSchema[None] = Field(
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
    error_message: Annotated[str, Field(min_length=1)] | SkipJsonSchema[None] = Field(
        default=None,
        description="If present - error loading context",
    )


class SourceInfo(str, Enum):
    PYPI = "pypi"
    SCRATCH = "scratch"

    def __str__(self):
        return self.value


class PackageInfo(BlueapiBaseModel):
    name: str = Field(description="Name of the package", default_factory=str)
    version: str = Field(description="Version of the package", default_factory=str)
    location: str = Field(description="Location of the package", default_factory=str)
    is_dirty: bool = Field(
        description="Does the package have uncommitted changes", default_factory=bool
    )
    source: SourceInfo = Field(
        description="Source of the package", default=SourceInfo.PYPI
    )


class PythonEnvironmentResponse(BlueapiBaseModel):
    """
    State of the Python environment.
    """

    installed_packages: list[PackageInfo] = Field(
        description="List of installed packages", default_factory=list
    )
    scratch_enabled: bool = Field(description="Scratch status", default=False)


class Cache(BlueapiBaseModel):
    """
    Represents the cached data required for managing authentication.
    """

    oidc_config: OIDCConfig
    access_token: str
    refresh_token: str
    id_token: str


class Health(str, Enum):
    OK = "ok"


class HealthProbeResponse(BlueapiBaseModel):
    status: Health

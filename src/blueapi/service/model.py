from enum import Enum
from typing import Iterable, List, Mapping, Type, Union

from bluesky.protocols import HasName
from dodal.utils import DependentDeviceInstantiationException, ExceptionInformation
from pydantic import Field

from blueapi.core import BLUESKY_PROTOCOLS, Device, Plan
from blueapi.utils import BlueapiBaseModel

_UNKNOWN_NAME = "UNKNOWN"


class _DeviceInformation(BlueapiBaseModel):
    device_type: type[Device] = Field(description="Concrete type of the device")
    protocols: List[str] = Field(
        description="Protocols that a device conforms to, indicating its capabilities"
    )


class DeviceModel(_DeviceInformation):
    """
    Representation of a device
    """

    name: str = Field(description="Name of the device")

    @classmethod
    def from_device(cls, device: Device) -> "DeviceModel":
        name = device.name if isinstance(device, HasName) else _UNKNOWN_NAME
        return cls(
            name=name, protocols=list(_protocol_names(device)), device_type=type(device)
        )


class FailedDeviceInstantiation(_DeviceInformation):
    """
    Representation of a device that either failed to be instantiated or was not
    attempted due to an earlier failure.
    """

    factory_name: str = Field(
        description="Name of a factory method that was not successfully called"
    )
    exception: Union[str, Mapping[str, str]] = Field(
        description="The exception that prevented this method from completing or a "
        "mapping of the name of factory methods that this method depended on to "
        "the exception that caused them to fail"
    )

    @classmethod
    def from_exception_informations(
        cls, factory_name: str, exc: ExceptionInformation
    ) -> "FailedDeviceInstantiation":
        exception = exc.exception
        exception_info: Union[str, Mapping[str, str]]
        if isinstance(exception, DependentDeviceInstantiationException):
            exception_info = {str(k): str(v) for k, v in exception.exceptions.values()}
        else:
            exception_info = f"{type(exception)}: {exception}"
        return cls(
            factory_name=factory_name,
            device_type=exc.return_type,
            protocols=list(_protocol_names(exc.return_type)),
            exception=exception_info,
        )


def _protocol_names(device: Union[Device, Type[Device]]) -> Iterable[str]:
    yield from (prot.__name__ for prot in BLUESKY_PROTOCOLS if isinstance(device, prot))


class DeviceRequest(BlueapiBaseModel):
    """
    A query for devices
    """

    ...


class DeviceResponse(BlueapiBaseModel):
    """
    Response to a query for devices
    """

    devices: List[DeviceModel] = Field(description="Devices available to use in plans")
    failed_devices: List[FailedDeviceInstantiation] = Field(
        description="Device creation methods that failed to run"
    )


class PlanModel(BlueapiBaseModel):
    """
    Representation of a plan
    """

    name: str = Field(description="Name of the plan")

    @classmethod
    def from_plan(cls, plan: Plan) -> "PlanModel":
        return cls(name=plan.name)


class PlanRequest(BlueapiBaseModel):
    """
    A query for plans
    """

    ...


class PlanResponse(BlueapiBaseModel):
    """
    Response to a query for plans
    """

    plans: List[PlanModel] = Field(description="Plans available to use by a worker")


class TaskResponse(BlueapiBaseModel):
    """
    Acknowledgement that a task has started, includes its ID
    """

    task_name: str = Field(description="Unique identifier for the task")

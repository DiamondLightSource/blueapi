import uuid
from dataclasses import dataclass, field
from typing import Iterable, List

from bluesky.protocols import HasName

from blueapi.core import BLUESKY_PROTOCOLS, Device, Plan

_UNKNOWN_NAME = "UNKNOWN"


@dataclass
class DeviceModel:
    """
    Representation of a device
    """

    name: str
    protocols: List[str]

    @classmethod
    def from_device(cls, device: Device) -> "DeviceModel":
        name = device.name if isinstance(device, HasName) else _UNKNOWN_NAME
        return cls(name, list(_protocol_names(device)))


def _protocol_names(device: Device) -> Iterable[str]:
    for protocol in BLUESKY_PROTOCOLS:
        if isinstance(device, protocol):
            yield protocol.__name__


@dataclass
class PlanModel:
    """
    Representation of a plan
    """

    name: str

    @classmethod
    def from_plan(cls, plan: Plan) -> "PlanModel":
        return cls(plan.name)


@dataclass
class TaskStarted:
    task_id: str

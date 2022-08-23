from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, List, Mapping

from bluesky.protocols import HasName

from blueapi.core import BLUESKY_PROTOCOLS, Device, Plan

_UNKNOWN_NAME = "UNKNOWN"


@dataclass
class DeviceModel:
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
    name: str

    @classmethod
    def from_plan(cls, plan: Plan) -> "PlanModel":
        return cls(plan.name)

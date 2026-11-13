from fastapi import APIRouter
from observability_utils.tracing import start_as_current_span

from blueapi.config import Tag
from blueapi.service import interface
from blueapi.service.model import DeviceModel, DeviceResponse

from .dependencies import TRACER, Runner

router = APIRouter(tags=[Tag.DEVICE])


@router.get("/devices")
@start_as_current_span(TRACER)
def get_devices(runner: Runner) -> DeviceResponse:
    """Retrieve information about all available devices."""
    devices = runner.run(interface.get_devices)
    return DeviceResponse(devices=devices)


@router.get("/devices/{name}")
@start_as_current_span(TRACER, "name")
def get_device_by_name(name: str, runner: Runner) -> DeviceModel:
    """Retrieve information about a devices by its (unique) name."""
    return runner.run(interface.get_device, name)

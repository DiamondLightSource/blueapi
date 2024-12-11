import logging
from collections.abc import Mapping
from types import ModuleType

from bluesky.run_engine import RunEngine
from dodal.utils import (
    AnyDevice,
    DeviceInitializationController,
    collect_factories,
    filter_ophyd_devices,
)
from ophyd_async.core import NotConnected
from ophyd_async.plan_stubs import ensure_connected

LOGGER = logging.getLogger(__name__)


def _report_successful_devices(
    devices: Mapping[str, AnyDevice],
    sim_backend: bool,
) -> None:
    sim_statement = " (sim mode)" if sim_backend else ""
    connected_devices = "\n".join(
        sorted([f"\t{device_name}" for device_name in devices.keys()])
    )

    LOGGER.info(f"{len(devices)} devices connected{sim_statement}:")
    LOGGER.info(connected_devices)


def _establish_device_connections(
    RE: RunEngine,
    devices: Mapping[str, AnyDevice],
    sim_backend: bool,
) -> tuple[Mapping[str, AnyDevice], Mapping[str, Exception]]:
    ophyd_devices, ophyd_async_devices = filter_ophyd_devices(devices)
    exceptions = {}

    # Connect ophyd devices
    for name, device in ophyd_devices.items():
        try:
            device.wait_for_connection()
        except Exception as ex:
            exceptions[name] = ex

    # Connect ophyd-async devices
    try:
        RE(ensure_connected(*ophyd_async_devices.values(), mock=sim_backend))
    except NotConnected as ex:
        exceptions = {**exceptions, **ex.sub_errors}

    # Only return the subset of devices that haven't raised an exception
    successful_devices = {
        name: device for name, device in devices.items() if name not in exceptions
    }
    return successful_devices, exceptions


def connect_devices(
    run_engine: RunEngine, module: ModuleType, devices: dict[str, AnyDevice], **kwargs
):
    factories = collect_factories(module, include_skipped=False)

    def is_simulated_device(name, factory, **kwargs):
        device = devices.get(name, None)
        mock_flag = kwargs.get("mock", kwargs.get("fake_with_ophyd_sim", False))
        return device is not None and (
            isinstance(factory, DeviceInitializationController)
            and (factory._mock or mock_flag)  # noqa: SLF001
            and isinstance(device, AnyDevice)
        )

    sim_devices = {
        name: devices.get(name)
        for name, factory in factories.items()
        if is_simulated_device(name, factory, **kwargs)
    }
    real_devices = {
        name: device
        for name, device in devices.items()
        if sim_devices.get(name, None) is None and (isinstance(device, AnyDevice))
    }

    if len(real_devices) > 0:
        real_devices, exceptions = _establish_device_connections(
            run_engine, real_devices, False
        )
        _report_successful_devices(real_devices, False)
    if len(sim_devices) > 0:
        sim_devices, _ = _establish_device_connections(run_engine, sim_devices, True)  # type: ignore
        _report_successful_devices(sim_devices, True)

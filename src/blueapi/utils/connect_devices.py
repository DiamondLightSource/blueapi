import logging
from collections.abc import Mapping
from typing import Any

LOGGER = logging.getLogger(__name__)


def report_successful_devices(
    devices: Mapping[str, Any],
    sim_backend: bool,
) -> None:
    sim_statement = " (sim mode)" if sim_backend else ""
    connected_devices = "\n".join(
        sorted([f"\t{device_name}" for device_name in devices.keys()])
    )

    LOGGER.info(f"{len(devices)} devices connected{sim_statement}:")
    LOGGER.info(connected_devices)

from typing import Any

import bluesky.plan_stubs as bps
import bluesky.plans as bp
from bluesky.protocols import Movable, Readable
from bluesky.utils import MsgGenerator
from dodal.common.coordination import inject

_DEFAULT_TEMPERATURE_CONTROLLER = inject("sample_temperature_controller")
_DEFAULT_PRESSURE_CONTROLLER = inject("sample_pressure_controller")


def temp_pressure_snapshot(
    detectors: list[Readable],
    temperature: Movable = _DEFAULT_TEMPERATURE_CONTROLLER,
    pressure: Movable = _DEFAULT_PRESSURE_CONTROLLER,
    target_temperature: float = 273.0,
    target_pressure: float = 10**5,
    metadata: dict[str, Any] | None = None,
) -> MsgGenerator:
    """
    Moves devices for pressure and temperature (defaults fetched from the context)
    and captures a single frame from a collection of devices
    Args:
        detectors: A list of devices to read while the sample is at STP
        temperature: A device controlling temperature of the sample,
            defaults to fetching a device name "sample_temperature" from the context
        pressure: A device controlling pressure on the sample,
            defaults to fetching a device name "sample_pressure" from the context
        target_pressure: target temperature in Kelvin. Default 273
        target_pressure: target pressure in Pa. Default 10**5
    Returns:
        MsgGenerator: Plan
    Yields:
        Iterator[MsgGenerator]: Bluesky messages
    """

    # Prepare sample environment
    yield from bps.abs_set(temperature, target_temperature, wait=True, group="init")
    yield from bps.abs_set(pressure, target_pressure, wait=True, group="init")
    yield from bps.wait(group="init")

    # Take data
    yield from bp.count(detectors, num=1, md=metadata or {})

import operator
from functools import reduce
from typing import Any, List, Mapping, Optional, Tuple, Type, Union

import bluesky.plans as bp
from apischema import serialize
from apischema.conversions.conversions import Conversion
from apischema.conversions.converters import AnyConversion, default_serialization
from bluesky.protocols import Movable, Readable
from cycler import Cycler, cycler
from scanspec.specs import Spec

from blueapi.core import MsgGenerator


def scan(
    detectors: List[Readable],
    spec: Spec[Movable],
    metadata: Optional[Mapping[str, Any]] = None,
) -> MsgGenerator:
    """
    Scan wrapping `bp.scan_nd`

    Args:
        detectors (List[Readable]): List of readable devices, will take a reading at
                                    each point
        spec (Spec[Movable]): ScanSpec modelling the path of the scan
        metadata (Optional[Mapping[str, Any]], optional): Key-value metadata to include
                                                          in exported data, defaults to
                                                          None.

    Returns:
        MsgGenerator: Plan

    Yields:
        Iterator[MsgGenerator]: Bluesky messages
    """

    metadata = {
        "detectors": [detector.name for detector in detectors],
        "scanspec": serialize(spec, default_conversion=_convert_devices),
        "shape": _shape(spec),
        **(metadata or {}),
    }

    cycler = _scanspec_to_cycler(spec)
    yield from bp.scan_nd(detectors, cycler, md=metadata)


# TODO: Use built-in scanspec utility method following completion of DAQ-4487
def _shape(spec: Spec[Movable]) -> Tuple[int, ...]:
    return tuple(len(dim) for dim in spec.calculate())


def _convert_devices(a_type: Type[Any]) -> Optional[AnyConversion]:
    if issubclass(a_type, Movable):
        return Conversion(str, source=a_type)
    else:
        return default_serialization(a_type)


def _scanspec_to_cycler(spec: Spec) -> Cycler:
    """
    Convert a scanspec to a cycler for compatibility with legacy Bluesky plans such as
    `bp.scan_nd`. Use the midpoints of the scanspec since cyclers are noramlly used
    for software triggered scans.

    Args:
        spec (Spec): A scanspec

    Returns:
        Cycler: A new cycler
    """

    midpoints = spec.frames().midpoints

    # Need to "add" the cyclers for all the axes together. The code below is
    # effectively: cycler(motor1, [...]) + cycler(motor2, [...]) + ...
    return reduce(operator.add, map(lambda args: cycler(*args), midpoints.items()))


def count(
    detectors: List[Readable],
    num: int = 1,
    delay: Optional[Union[float, List[float]]] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> MsgGenerator:
    """
    Take `n` readings from a device

    Args:
        detectors (List[Readable]): Readable devices to read
        num (int, optional): Number of readings to take. Defaults to 1.
        delay (Optional[Union[float, List[float]]], optional): Delay between readings.
                                                               Defaults to None.
        metadata (Optional[Mapping[str, Any]], optional): Key-value metadata to include
                                                          in exported data.
                                                          Defaults to None.

    Returns:
        MsgGenerator: _description_

    Yields:
        Iterator[MsgGenerator]: _description_
    """

    yield from bp.count(detectors, num, delay=delay, md=metadata)

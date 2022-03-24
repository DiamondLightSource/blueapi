import operator
from functools import reduce
from typing import Any, List, Mapping, Optional, Union

import bluesky.plans as bp
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

    :param detectors: List of readable devices, will take a reading at each point
    :param spec: ScanSpec modelling the path of the scan
    :param metadata: Key-value metadata to include in exported data, defaults to None
    :return: A plan
    """

    metadata = {"detectors": detectors, "scanspec": spec, **(metadata or {})}

    cycler = scanspec_to_cycler(spec)
    yield from bp.scan_nd(detectors, cycler, md=metadata)


def scanspec_to_cycler(spec: Spec) -> Cycler:
    """
    Convert a scanspec to a cycler for compatibility with legacy Bluesky plans such as
    `bp.scan_nd`. Use the midpoints of the scanspec since cyclers are noramlly used
    for software triggered scans.

    :param spec: A scanspec
    :return: A cycler with the axes of the spec mapping to the midpoints.
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

    :param detectors: Readable devices to read
    :param num: Number of readings to take, defaults to 1
    :param delay: Delay between readings, defaults to None
    :param metadata: Key-value metadata to include in exported data, defaults to None
    :return: A plan
    """

    yield from bp.count(detectors, num, delay=delay, md=metadata)

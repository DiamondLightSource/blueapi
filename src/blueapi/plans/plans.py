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
    axes_to_move: Mapping[str, Movable],
    spec: Spec[str],
    metadata: Optional[Mapping[str, Any]] = None,
) -> MsgGenerator:
    """
    Scan wrapping `bp.scan_nd`

    Args:
        detectors: List of readable devices, will take a reading at
                                    each point
        axes_to_move: All axes involved in this scan, names and
            objects
        spec: ScanSpec modelling the path of the scan
        metadata: Key-value metadata to include
                                                          in exported data, defaults to
                                                          None.

    Returns:
        MsgGenerator: Plan

    Yields:
        Iterator[MsgGenerator]: Bluesky messages
    """

    _md = {
        "plan_args": {
            "detectors": list(map(repr, detectors)),
            "axes_to_move": {k: repr(v) for k, v in axes_to_move.items()},
            "spec": repr(spec),
        },
        "plan_name": "scan",
        "shape": spec.shape(),
        **(metadata or {}),
    }

    cycler = _scanspec_to_cycler(spec, axes_to_move)
    yield from bp.scan_nd(detectors, cycler, md=_md)


def _scanspec_to_cycler(spec: Spec[str], axes: Mapping[str, Movable]) -> Cycler:
    """
    Convert a scanspec to a cycler for compatibility with legacy Bluesky plans such as
    `bp.scan_nd`. Use the midpoints of the scanspec since cyclers are normally used
    for software triggered scans.

    Args:
        spec: A scanspec
        axes: Names and axes to move

    Returns:
        Cycler: A new cycler
    """

    midpoints = spec.frames().midpoints
    midpoints = {axes[name]: points for name, points in midpoints.items()}

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
    plan_args = (
        {  # If bp.count added delay to plan_args, we could remove all md handling
            "detectors": list(map(repr, detectors)),
            "num": num,
            "delay": delay,
        }
    )

    _md = {
        "plan_args": plan_args,
        **(metadata or {}),
    }

    yield from bp.count(detectors, num, delay=delay, md=_md)

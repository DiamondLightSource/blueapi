import operator
from collections.abc import Mapping
from functools import reduce
from typing import Annotated, Any

import bluesky.plans as bp
from bluesky.protocols import HasName, Movable, Readable
from cycler import Cycler, cycler
from dodal.common import MsgGenerator
from dodal.plans.data_session_metadata import attach_data_session_metadata_decorator
from pydantic import Field, validate_call
from scanspec.specs import Spec

"""
Plans related to the use of the `ScanSpec https://github.com/dls-controls/scanspec`
library for constructing arbitrarily complex N-dimensional trajectories, similar to
Diamond's "mapping scans" using ScanPointGenerator.
"""


class NamedMovable(HasName, Movable): ...


PositiveFloat = Annotated[float, Field(gt=0)]


@attach_data_session_metadata_decorator()
@validate_call(config={"arbitrary_types_allowed": True})
def scan(
    detectors: Annotated[
        set[Readable], "Set of readable devices, will take a reading at each point"
    ],
    axes_to_move: Annotated[
        Mapping[str, NamedMovable], "All axes involved in this scan, names and objects"
    ],
    spec: Annotated[Spec[str], "ScanSpec modelling the path of the scan"],
    metadata: Mapping[str, Any] | None = None,
) -> MsgGenerator:
    _md = {
        "plan_args": {
            "detectors": {det.name for det in detectors},
            "axes_to_move": {k: v.name for k, v in axes_to_move.items()},
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
    return reduce(operator.add, (cycler(*args) for args in midpoints.items()))


@attach_data_session_metadata_decorator()
@validate_call(config={"arbitrary_types_allowed": True})
def count(
    detectors: Annotated[
        set[Readable],
        "Set of readable devices, will take a reading at each point",
        Field(min_items=1),
    ],
    num: Annotated[int, "Number of frames to collect", Field(ge=1)] = 1,
    delay: Annotated[
        PositiveFloat | list[PositiveFloat] | None,
        "Delay between readings: if list, len(delay) == num - 1 and the delay is \
            between each point, if value or None is the delay for every gap",
    ] = None,
    metadata: Mapping[str, Any] | None = None,
) -> MsgGenerator:
    yield from bp.count(detectors, num, delay=delay, md=metadata or {})

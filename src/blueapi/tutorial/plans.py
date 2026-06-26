from collections.abc import Sequence
from typing import Annotated, Any

import bluesky.plans as bp
from bluesky.protocols import Readable
from bluesky.utils import MsgGenerator
from ophyd_async.core import AsyncReadable
from pydantic import Field, NonNegativeFloat, validate_call


@validate_call(config={"arbitrary_types_allowed": True})
def count(
    detectors: Annotated[
        Sequence[Readable | AsyncReadable],
        Field(
            description="Set of readable devices, will take a reading at each point",
            min_length=1,
        ),
    ],
    num: Annotated[int, Field(description="Number of frames to collect", ge=1)] = 1,
    delay: Annotated[
        NonNegativeFloat | Sequence[NonNegativeFloat],
        Field(
            description="Delay between readings: if tuple, len(delay) == num - 1 and \
            the delays are between each point, if value or None is the delay for every \
            gap",
            json_schema_extra={"units": "s"},
        ),
    ] = 0.0,
    metadata: dict[str, Any] | None = None,
) -> MsgGenerator:
    """Reads from a number of devices.

    Wraps bluesky.plans.count(det, num, delay, md=metadata) exposing only serializable
    parameters and metadata.
    """
    if isinstance(delay, Sequence):
        assert len(delay) == num - 1, (
            f"Number of delays given must be {num - 1}: was given {len(delay)}"
        )
    metadata = metadata or {}
    metadata["shape"] = (num,)
    yield from bp.count(tuple(detectors), num, delay=delay, md=metadata)

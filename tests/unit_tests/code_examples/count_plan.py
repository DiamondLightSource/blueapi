from collections.abc import Iterable
from typing import Any

import bluesky.plans as bp
from bluesky.protocols import Readable
from bluesky.utils import MsgGenerator
from dodal.common.coordination import inject

_DEFAULT_DETECTORS = [inject("my_detector")]


def count(
    detectors: list[Readable] = _DEFAULT_DETECTORS,
    num: int = 1,
    delay: float | Iterable[float] = 0.0,
    metadata: dict[str, Any] | None = None,
) -> MsgGenerator:
    """
    Take `n` readings from a collection of detectors

    Args:
        detectors (List[Readable]): Readable devices to read: when being run in Blueapi
                                    defaults to fetching a device named "det" from its
                                    context, else will require to be overridden.
        num (int, optional): Number of readings to take. Defaults to 1.
        delay (Optional[Union[float, List[float]]], optional): Delay between readings.
                                                            Defaults to None.
        metadata (Optional[dict[str, Any]], optional): Key-value metadata to include
                                                        in exported data.
                                                        Defaults to None.

    Returns:
        MsgGenerator: _description_

    Yields:
        Iterator[MsgGenerator]: _description_
    """

    yield from bp.count(detectors, num, delay=delay, md=metadata)

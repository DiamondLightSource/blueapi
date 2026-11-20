import logging

import bluesky.plans as bp
from bluesky.protocols import Readable
from bluesky.utils import MsgGenerator

LOGGER = logging.getLogger(__name__)


def count_with_optional_monitor(
    detector: Readable, monitor: Readable | str, num: int = 1
) -> MsgGenerator[None]:
    detectors = [detector]
    # Check before doing anything else: if no Readable device has the name that
    # was requested, the name itself is passed in as a string
    if isinstance(monitor, Readable):
        detectors.append(monitor)
    else:
        LOGGER.warning("Monitor '%s' is not available, counting without it", monitor)

    yield from bp.count(detectors, num=num)

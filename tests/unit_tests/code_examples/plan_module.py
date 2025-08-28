from typing import Any

from bluesky.protocols import Movable, Readable
from bluesky.utils import MsgGenerator


def my_plan(
    detector: Readable,
    motor: Movable,
    steps: int,
    sample_name: str,
    extra_metadata: dict[str, Any],
) -> MsgGenerator[None]:
    # logic goes here
    ...

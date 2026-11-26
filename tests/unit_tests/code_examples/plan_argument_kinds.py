from bluesky.protocols import Readable
from bluesky.utils import MsgGenerator


def repeated_read(
    repeats: int,
    /,
    delay: float,
    *detectors: Readable,
    wait: bool = False,
    **labels: str,
) -> MsgGenerator[None]:
    yield from ()

from typing import Any

import bluesky.plans as bp
from bluesky.protocols import Readable
from bluesky.utils import MsgGenerator


def pass_metadata(
    det: Readable,
    metadata: dict[str, Any] | None = None,
) -> MsgGenerator:
    yield from bp.count([det], md=metadata or {})

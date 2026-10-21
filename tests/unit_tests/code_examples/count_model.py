from collections.abc import Iterable
from typing import Any

from bluesky.protocols import Readable
from dodal.common.coordination import inject
from pydantic import BaseModel, ConfigDict

_DEFAULT_DETECTORS = [inject("my_detector")]


class CountParameters(BaseModel):
    detectors: list[Readable] = _DEFAULT_DETECTORS
    num: int = 1
    delay: float | Iterable[float] = 0.0
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
        validate_default=True,
    )

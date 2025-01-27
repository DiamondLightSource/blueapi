from collections.abc import Generator
from typing import Any, TypeVar

from bluesky.utils import Msg

P = TypeVar("P")
OtherMsgGenerator = Generator[Msg, Any, Any]
OtherParametrizedMsgGenerator = Generator[Msg, Any, P]

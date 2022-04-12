import inspect
from typing import Type

from .base import MessageListener


def _determine_deserialization_type(
    listener: MessageListener, default: Type = str
) -> Type:

    _, message = inspect.signature(listener).parameters.values()
    a_type = message.annotation
    if a_type is not inspect.Parameter.empty:
        return a_type
    else:
        return default

import inspect
from typing import Type

from .base import MessageListener


def determine_deserialization_type(
    listener: MessageListener, default: Type = str
) -> Type:
    """
    Inspect a message listener function to determine the type to deserialize
    a message to

    Args:
        listener (MessageListener): The function that takes a deserialized message
        default (Type, optional): If the type cannot be determined, what default
                                  should we fall back on? Defaults to str.

    Returns:
        Type: _description_
    """

    _, message = inspect.signature(listener).parameters.values()
    a_type = message.annotation
    if a_type is not inspect.Parameter.empty:
        return a_type
    else:
        return default

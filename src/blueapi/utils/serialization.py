from typing import Any

from pydantic import BaseModel


def serialize(obj: Any) -> Any:
    """
    Pydantic-aware serialization routine that can also be
    used on primitives. So serialize(4) is 4, but
    serialize(<model>) is a dictionary.

    Args:
        obj: The object to serialize

    Returns:
        Any: The serialized object
    """

    if isinstance(obj, BaseModel):
        return obj.dict()
    elif hasattr(obj, "__pydantic_model__"):
        return serialize(getattr(obj, "__pydantic_model__"))
    else:
        return obj

import json
import re
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
        # Serialize by alias so that our camelCase models leave the service
        # with camelCase field names
        return obj.model_dump(by_alias=True)
    elif hasattr(obj, "__pydantic_model__"):
        return serialize(obj.__pydantic_model__)
    else:
        return obj


_INSTRUMENT_SESSION_AUTHZ_REGEX: re.Pattern = re.compile(
    r"^[a-zA-Z]{2}(?P<proposal>\d+)-(?P<visit>\d+)$"
)


def access_blob(instrument_session: str, beamline: str) -> str:
    m = _INSTRUMENT_SESSION_AUTHZ_REGEX.match(instrument_session)
    if m is None:
        raise ValueError(
            "Unable to extract proposal and visit from "
            f"instrument session {instrument_session}"
        )
    blob = {
        "proposal": int(m["proposal"]),
        "visit": int(m["visit"]),
        "beamline": beamline,
    }
    return json.dumps(blob)

import json
from typing import Any

from pydantic import BaseModel

from blueapi import utils


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


def access_blob(instrument_session: str, beamline: str) -> str:
    session_match = utils.INSTRUMENT_SESSION_RE.match(instrument_session)
    proposal_match = utils.TILED_PROPOSAL_RE.match(instrument_session)
    if session_match is None or proposal_match is None:
        raise ValueError(
            "Unable to extract proposal and visit from "
            f"instrument session {instrument_session}"
        )
    blob = {
        # The full proposal code (e.g. "cm12345"), not just its number - the
        # tiled access policy strips the letters itself where it needs them.
        "proposal": proposal_match["proposal"],
        "visit": int(session_match["visit"]),
        "beamline": beamline,
    }
    return json.dumps(blob)

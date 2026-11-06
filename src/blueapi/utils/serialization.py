from typing import Any, Literal

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


TiledFolder = Literal["raw", "processed", "processing"]

#: The folders of a visit in tiled, see the dls-tiled access policy
TILED_FOLDERS: tuple[TiledFolder, ...] = ("raw", "processed", "processing")


def access_blob(
    instrument_session: str, instrument: str, folder: TiledFolder = "raw"
) -> dict[str, Any]:
    """The access blob asking tiled's access policy to tag a node as part of
    the given folder of a visit."""
    if utils.INSTRUMENT_SESSION_RE.match(instrument_session) is None:
        raise ValueError(
            "Unable to extract proposal and visit from "
            f"instrument session {instrument_session}"
        )
    return {
        "instrument": instrument,
        "instrument_session": instrument_session,
        "folder": folder,
    }

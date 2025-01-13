from typing import Any

from bluesky.callbacks.tiled_writer import TiledWriter
from tiled.client import from_uri

from blueapi.config import TiledConfig
from blueapi.core.bluesky_types import DataEvent


class TiledConverter:
    def __init__(self, uri: str, headers: dict[str, Any]):
        self._writer: TiledWriter = TiledWriter(from_uri(uri, headers=headers))

    def __call__(self, data: DataEvent, _: str | None = None) -> None:
        self._writer(data.name, data.doc)


class TiledConnection:
    def __init__(self, config: TiledConfig):
        self.uri = f"{config.host}:{config.port}"

    def __call__(self, token: str | None):
        return TiledConverter(
            self.uri, headers={"Authorization": f"Bearer {token}"} if token else {}
        )

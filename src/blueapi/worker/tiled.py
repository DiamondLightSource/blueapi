from bluesky.callbacks.tiled_writer import TiledWriter
from httpx import Headers
from tiled.client import from_context
from tiled.client.context import Context as TiledContext

from blueapi.config import TiledConfig
from blueapi.core.bluesky_types import DataEvent


class TiledConverter:
    def __init__(self, tiled_context: TiledContext):
        self._writer: TiledWriter = TiledWriter(from_context(tiled_context))

    def __call__(self, data: DataEvent, _: str | None = None) -> None:
        self._writer(data.name, data.doc)


class TiledConnection:
    def __init__(self, config: TiledConfig):
        self.uri = f"{config.host}:{config.port}"

    def __call__(self, headers: Headers | None):
        return TiledConverter(TiledContext(self.uri, headers=headers))

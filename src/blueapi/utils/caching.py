from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import TypeAdapter

DEFAULT_CACHE_DIR = Path("~/.cache/").expanduser()

T = TypeVar("T")


class DiskCacheManager(Generic[T]):
    def __init__(self, path: Path) -> None:
        self._path = path

    def save_cache(self, cache: T) -> None:
        self.delete_cache()
        with open(self._path, "xb") as token_file:
            as_json = TypeAdapter(T).dump_json(cache)
            token_file.write(base64.b64encode(as_json))
        os.chmod(self._path, 0o600)

    def load_cache(self) -> T:
        with open(self._path, "rb") as cache_file:
            return TypeAdapter(T).validate_json(
                base64.b64decode(cache_file.read()).decode("utf-8")
            )

    def delete_cache(self) -> None:
        Path(self._path).unlink(missing_ok=True)

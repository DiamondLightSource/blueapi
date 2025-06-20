from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any, TypeVar

from pydantic import TypeAdapter

T = TypeVar("T")


def default_cache_dir() -> Path:
    cache_path = Path(os.environ.get("XDG_CACHE_HOME", "~/.cache/")).expanduser()
    return cache_path / "blueapi_cache.d"


class DiskCache:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or default_cache_dir()

    def set(self, key: str, value: Any) -> None:
        self._ensure_root()
        path = self._path_to_value(key)
        path.unlink(missing_ok=True)
        with path.open("xb") as writer:
            as_json = TypeAdapter(T).dump_json(value)
            writer.write(base64.b64encode(as_json))
        os.chmod(path, 0o600)

    def get(
        self,
        key: str,
        deserialize_type: type[T] = str,
        default: T | None = None,
    ) -> T | None:
        path = self._path_to_value(key)
        if path.exists():
            with path.open("rb") as reader:
                return TypeAdapter(deserialize_type).validate_json(
                    base64.b64decode(reader.read()).decode("utf-8")
                )
        else:
            return default

    def _ensure_root(self) -> None:
        os.makedirs(self._path, exist_ok=True)

    def _path_to_value(self, key: str) -> Path:
        return self._path / key

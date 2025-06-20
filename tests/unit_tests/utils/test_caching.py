import os
from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from blueapi.utils.caching import DiskCache


@pytest.fixture
def root() -> Generator[Path]:
    temporary_directory = TemporaryDirectory()
    yield Path(temporary_directory.name)
    temporary_directory.cleanup()


@pytest.fixture
def some_file(root: Path) -> Generator[Path]:
    file_path = root / "temp"
    with file_path.open("w") as stream:
        stream.write("foo")
    yield file_path
    os.remove(file_path)


@pytest.fixture
def cache(root: Path) -> DiskCache:
    return DiskCache(root)


def test_caches_to_correct_file_path(cache: DiskCache, root: Path):
    assert not (root / "foo").exists()
    cache.set("foo", "bar")
    assert (root / "foo").exists()


def test_writes_b64_encoded_string(cache: DiskCache, root: Path):
    cache.set("foo", "bar")
    with (root / "foo").open("rb") as reader:
        assert reader.read() == b"ImJhciI="


@pytest.mark.parametrize("key", ["foo", "bar", "baz"])
def test_decodes_b64_and_reads_back(cache: DiskCache, key: str):
    cache.set(key, "bar")
    assert cache.get(key) == "bar"


def test_overwrites(cache: DiskCache):
    cache.set("foo", "bar")
    assert cache.get("foo") == "bar"
    cache.set("foo", "baz")
    assert cache.get("foo") == "baz"


@pytest.mark.parametrize("value", [1, True, {"foo": "bar"}, [1, 2]])
def test_default_rejects_invalid_string(cache: DiskCache, value: Any):
    cache.set("foo", value)
    with pytest.raises(ValidationError):
        assert cache.get("foo")


@pytest.mark.parametrize(
    "value,expected_type",
    [
        (1, int),
        (True, bool),
        ({"foo": "bar"}, dict[str, str]),
        ([1, 2], list[int]),
    ],
)
def test_deserializes_value(cache: DiskCache, value: Any, expected_type: type[Any]):
    cache.set("foo", value)
    assert cache.get("foo", deserialize_type=expected_type) == value


def test_defaults_to_none(cache: DiskCache):
    assert cache.get("foo") is None


@pytest.mark.parametrize("default", [1, True, {"foo": "bar"}, [1, 2]])
def test_defaults_to_default(cache: DiskCache, default: Any):
    assert cache.get("foo", default=default) == default


@patch("pathlib.io.open")
@patch("blueapi.utils.caching.os.makedirs")
def test_makes_directory_on_set(mock_makedirs: Mock, _: Mock):
    cache = DiskCache(Path("/cacheroot"))
    cache.set("foo", "bar")
    mock_makedirs.assert_called_once_with(Path("/cacheroot"), exist_ok=True)


def test_fails_if_directory_is_a_file(some_file: Path):
    cache = DiskCache(some_file)
    with pytest.raises(FileExistsError):
        cache.set("foo", "bar")

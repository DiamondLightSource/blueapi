import stat
from pathlib import Path
from unittest.mock import Mock

import pytest

from blueapi.utils import get_owner_gid, is_sgid_set


@pytest.mark.parametrize(
    "bits",
    [
        # Files
        0o10_0600,  # -rw-------.
        0o10_0777,  # -rwxrwxrwx.
        0o10_0000,  # ----------.
        0o10_0644,  # -rw-r--r--.
        0o10_0400,  # -r--------.
        0o10_0666,  # -rw-rw-rw-.
        0o10_0444,  # -r--r--r--.
        # Directories
        0o04_0777,  # drwxrwxrwx.
        0o04_0000,  # d---------.
        0o04_0600,  # drw-------.
    ],
    ids=lambda p: f"{p:06o} ({stat.filemode(p)})",
)
def test_is_sgid_set_should_be_disabled(bits: int):
    assert not _mocked_is_sgid_set(bits)


@pytest.mark.parametrize(
    "bits",
    [
        # Files
        0o10_2777,  # -rwxrwsrwx.
        0o10_2000,  # ------S---.
        0o10_2644,  # -rw-r-Sr--.
        0o10_2600,  # -rw---S---.
        0o10_2400,  # -r----S---.
        0o10_2666,  # -rw-rwSrw-.
        0o10_2444,  # -r--r-Sr--.
        # Directories
        0o04_2777,  # drwxrwsrwx.
        0o04_2000,  # d-----S---.
        0o04_2600,  # drw---S---.
    ],
    ids=lambda p: f"{p:06o} ({stat.filemode(p)})",
)
def test_is_sgid_set_should_be_enabled(bits: int):
    assert _mocked_is_sgid_set(bits)


def _mocked_is_sgid_set(bits: int) -> bool:
    path = Mock(spec=Path)
    path.stat().st_mode = bits

    return is_sgid_set(path)


def test_get_owner_gid():
    path = Mock(spec=Path)
    path.stat().st_gid = 12345

    assert get_owner_gid(path) == 12345

from pathlib import Path
from unittest.mock import Mock

import pytest

from blueapi.utils import get_owner_gid, is_sgid_set


@pytest.mark.parametrize(
    "bits",
    [
        33152,  # -rw-------.
        33279,  # -rwxrwxrwx.
        32768,  # ----------.
        33188,  # -rw-r--r--.
        33024,  # -r--------.
        33206,  # -rw-rw-rw-.
        33060,  # -r--r--r--.
        16895,  # drwxrwxrwx.
        16384,  # d---------.
        16768,  # drw-------.
    ],
)
def test_is_sgid_set_should_be_disabled(bits: int):
    assert not _mocked_is_sgid_set(bits)


@pytest.mark.parametrize(
    "bits",
    [
        34303,  # -rwxrwsrwx.
        33792,  # ------S---.
        34212,  # -rw-r-Sr--.
        34176,  # -rw---S---.
        34048,  # -r----S---.
        34230,  # -rw-rwSrw-.
        34084,  # -r--r-Sr--.
        17919,  # drwxrwsrwx.
        17408,  # d-----S---.
        17792,  # drw---S---.
    ],
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

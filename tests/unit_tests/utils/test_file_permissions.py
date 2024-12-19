from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from blueapi.utils import is_sgid_enabled


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
@patch("blueapi.utils.file_permissions.os.stat")
def test_is_sgid_enabled_should_be_disabled(mock_stat: Mock, bits: int):
    assert not _mocked_is_sgid_enabled(mock_stat, bits)


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
@patch("blueapi.utils.file_permissions.os.stat")
def test_is_sgid_enabled_should_be_enabled(mock_stat: Mock, bits: int):
    assert _mocked_is_sgid_enabled(mock_stat, bits)


def _mocked_is_sgid_enabled(mock_stat: Mock, bits: int) -> bool:
    (mock_stat_for_file := Mock()).st_mode = bits
    mock_stat.return_value = mock_stat_for_file
    return is_sgid_enabled(Path("/doesnt/matter"))

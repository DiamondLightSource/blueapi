import subprocess
import sys
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from blueapi.service.scratch import PipShim, ScratchManager


@pytest.fixture
def pip() -> MagicMock:
    return MagicMock()


@pytest.fixture
def scratch_directory() -> MagicMock:
    return MagicMock()


@pytest.fixture
def manager(
    scratch_directory: Path,
    pip: PipShim,
) -> ScratchManager:
    return ScratchManager(scratch_directory, True, pip)


@pytest.fixture
def non_auto_manager(
    scratch_directory: Path,
    pip: PipShim,
) -> ScratchManager:
    return ScratchManager(scratch_directory, False, pip)


def test_errors_when_no_scratch_directory_and_not_allowed_to_auto_make(
    scratch_directory: MagicMock,
    non_auto_manager: ScratchManager,
) -> None:
    scratch_directory.is_file.return_value = False
    scratch_directory.exists.return_value = False
    with pytest.raises(FileNotFoundError):
        non_auto_manager.sync_packages()


def test_errors_when_scratch_path_is_a_file_and_not_allowed_to_auto_make(
    non_auto_manager: ScratchManager,
) -> None:
    with pytest.raises(FileExistsError):
        non_auto_manager.sync_packages()


def test_errors_when_scratch_path_is_a_file_and_allowed_to_auto_make(
    manager: ScratchManager,
) -> None:
    with pytest.raises(FileExistsError):
        manager.sync_packages()


def test_auto_make_directory(
    scratch_directory: MagicMock,
    manager: ScratchManager,
) -> None:
    scratch_directory.is_file.return_value = False
    scratch_directory.exists.return_value = False
    with patch("blueapi.service.scratch.os.listdir"):
        manager.sync_packages()
    scratch_directory.mkdir.assert_called_once()


@pytest.mark.parametrize(
    "subdirectories",
    [
        [],
        ["foo"],
        ["foo", "bar"],
    ],
)
def test_does_pip_install(
    scratch_directory: MagicMock,
    pip: MagicMock,
    manager: ScratchManager,
    subdirectories: List[str],
) -> None:
    scratch_directory.is_file.return_value = False
    with patch("blueapi.service.scratch.os.listdir") as listdir:
        listdir.return_value = subdirectories
        manager.sync_packages()

    if len(subdirectories) > 0:
        for directory in subdirectories:
            inp = scratch_directory / directory
            pip.install_editable.assert_called_once_with(inp, [])
    else:
        pip.install_editable.assert_not_called()


def test_handles_install_error(
    scratch_directory: MagicMock,
    pip: MagicMock,
    manager: ScratchManager,
) -> None:
    scratch_directory.is_file.return_value = False
    pip.install_editable.side_effect = [
        None,
        subprocess.CalledProcessError(1, ["foo", "bar"]),
        None,
    ]
    with patch("blueapi.service.scratch.os.listdir") as listdir:
        listdir.return_value = ["foo", "bar", "baz"]
        manager.sync_packages()


def test_pip_shim_no_extras() -> None:
    pip = PipShim()

    with patch("blueapi.service.scratch.subprocess.check_call") as check_call:
        pip.install_editable(Path("/foo/bar"), [])
        check_call.assert_called_once_with(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "-e",
                "/foo/bar",
            ]
        )


def test_pip_shim_with_extras() -> None:
    pip = PipShim()

    with patch("blueapi.service.scratch.subprocess.check_call") as check_call:
        pip.install_editable(Path("/foo/bar"), ["dev", "shim"])
        check_call.assert_called_once_with(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "-e",
                "/foo/bar[dev,shim]",
            ]
        )

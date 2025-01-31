import os
import stat
import uuid
from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, call, patch

import pytest

from blueapi.cli.scratch import ensure_repo, scratch_install, setup_scratch
from blueapi.config import ScratchConfig, ScratchRepository
from blueapi.utils import get_owner_gid


@pytest.fixture
def directory_path() -> Generator[Path]:
    temporary_directory = TemporaryDirectory()
    yield Path(temporary_directory.name)
    temporary_directory.cleanup()


@pytest.fixture
def directory_path_with_sgid(directory_path: Path) -> Path:
    os.chmod(
        directory_path,
        os.stat(directory_path).st_mode + stat.S_ISGID,
    )
    return directory_path


@pytest.fixture
def file_path(directory_path_with_sgid: Path) -> Generator[Path]:
    file_path = directory_path_with_sgid / str(uuid.uuid4())
    with file_path.open("w") as stream:
        stream.write("foo")
    yield file_path
    os.remove(file_path)


@pytest.fixture
def nonexistant_path(directory_path_with_sgid: Path) -> Path:
    file_path = directory_path_with_sgid / str(uuid.uuid4())
    assert not file_path.exists()
    return file_path


@patch("blueapi.cli.scratch.Popen")
def test_scratch_install_installs_path(
    mock_popen: Mock,
    directory_path_with_sgid: Path,
):
    mock_process = Mock()
    mock_process.returncode = 0
    mock_popen.return_value = mock_process

    scratch_install(directory_path_with_sgid, timeout=1.0)

    mock_popen.assert_called_once_with(
        [
            "python",
            "-m",
            "pip",
            "install",
            "--no-deps",
            "-e",
            str(directory_path_with_sgid),
        ]
    )


def test_scratch_install_fails_on_file(file_path: Path):
    with pytest.raises(KeyError):
        scratch_install(file_path, timeout=1.0)


def test_scratch_install_fails_on_nonexistant_path(nonexistant_path: Path):
    with pytest.raises(KeyError):
        scratch_install(nonexistant_path, timeout=1.0)


@patch("blueapi.cli.scratch.Popen")
@pytest.mark.parametrize("code", [1, 2, 65536])
def test_scratch_install_fails_on_non_zero_exit_code(
    mock_popen: Mock,
    directory_path_with_sgid: Path,
    code: int,
):
    mock_process = Mock()
    mock_process.returncode = code
    mock_popen.return_value = mock_process

    with pytest.raises(RuntimeError):
        scratch_install(directory_path_with_sgid, timeout=1.0)


@patch("blueapi.cli.scratch.Repo")
def test_repo_not_cloned_and_validated_if_found_locally(
    mock_repo: Mock,
    directory_path_with_sgid: Path,
):
    ensure_repo("http://example.com/foo.git", directory_path_with_sgid)
    mock_repo.assert_called_once_with(directory_path_with_sgid)
    mock_repo.clone_from.assert_not_called()


@patch("blueapi.cli.scratch.Repo")
def test_repo_cloned_if_not_found_locally(
    mock_repo: Mock,
    nonexistant_path: Path,
):
    ensure_repo("http://example.com/foo.git", nonexistant_path)
    mock_repo.assert_not_called()
    mock_repo.clone_from.assert_called_once_with(
        "http://example.com/foo.git", nonexistant_path
    )


@patch("blueapi.cli.scratch.Repo")
def test_repo_cloned_with_correct_umask(
    mock_repo: Mock,
    directory_path_with_sgid: Path,
):
    repo_root = directory_path_with_sgid / "foo"
    file_path = repo_root / "a"

    def write_repo_files():
        repo_root.mkdir()
        with file_path.open("w") as stream:
            stream.write("foo")

    mock_repo.clone_from.side_effect = lambda url, path: write_repo_files()

    ensure_repo("http://example.com/foo.git", repo_root)
    assert file_path.exists()
    assert file_path.is_file()
    st = os.stat(file_path)
    assert st.st_mode & stat.S_IWGRP


def test_repo_discovery_errors_if_file_found_with_repo_name(file_path: Path):
    with pytest.raises(KeyError):
        ensure_repo("http://example.com/foo.git", file_path)


def test_setup_scratch_fails_on_nonexistant_root(
    nonexistant_path: Path,
):
    config = ScratchConfig(root=nonexistant_path, repositories=[])
    with pytest.raises(KeyError):
        setup_scratch(config)


def test_setup_scratch_fails_on_non_directory_root(
    file_path: Path,
):
    config = ScratchConfig(root=file_path, repositories=[])
    with pytest.raises(KeyError):
        setup_scratch(config)


def test_setup_scratch_fails_on_non_sgid_root(
    directory_path: Path,
):
    config = ScratchConfig(root=directory_path, repositories=[])
    with pytest.raises(PermissionError):
        setup_scratch(config)


def test_setup_scratch_fails_on_wrong_gid(
    directory_path_with_sgid: Path,
):
    config = ScratchConfig(
        root=directory_path_with_sgid,
        required_gid=12345,
        repositories=[],
    )
    assert get_owner_gid(directory_path_with_sgid) != 12345
    with pytest.raises(PermissionError):
        setup_scratch(config)


@pytest.mark.skip(
    reason="""
We can't chown a tempfile in all environments, in particular it
seems to be broken in GH actions at the moment. We should
rewrite these tests to use mocks.

See https://github.com/DiamondLightSource/blueapi/issues/770
"""
)
def test_setup_scratch_succeeds_on_required_gid(
    directory_path_with_sgid: Path,
):
    # We may not own the temp root in some environments
    root = directory_path_with_sgid / "a-root"
    os.makedirs(root)
    os.chown(root, uid=12345, gid=12345)
    config = ScratchConfig(
        root=root,
        required_gid=12345,
        repositories=[],
    )
    assert get_owner_gid(root) == 12345
    setup_scratch(config)


@patch("blueapi.cli.scratch.ensure_repo")
@patch("blueapi.cli.scratch.scratch_install")
def test_setup_scratch_iterates_repos(
    mock_scratch_install: Mock,
    mock_ensure_repo: Mock,
    directory_path_with_sgid: Path,
):
    config = ScratchConfig(
        root=directory_path_with_sgid,
        repositories=[
            ScratchRepository(
                name="foo",
                remote_url="http://example.com/foo.git",
            ),
            ScratchRepository(
                name="bar",
                remote_url="http://example.com/bar.git",
            ),
        ],
    )
    setup_scratch(config, install_timeout=120.0)

    mock_ensure_repo.assert_has_calls(
        [
            call("http://example.com/foo.git", directory_path_with_sgid / "foo"),
            call("http://example.com/bar.git", directory_path_with_sgid / "bar"),
        ]
    )

    mock_scratch_install.assert_has_calls(
        [
            call(directory_path_with_sgid / "foo", timeout=120.0),
            call(directory_path_with_sgid / "bar", timeout=120.0),
        ]
    )


@patch("blueapi.cli.scratch.ensure_repo")
@patch("blueapi.cli.scratch.scratch_install")
def test_setup_scratch_continues_after_failure(
    mock_scratch_install: Mock,
    mock_ensure_repo: Mock,
    directory_path_with_sgid: Path,
):
    config = ScratchConfig(
        root=directory_path_with_sgid,
        repositories=[
            ScratchRepository(
                name="foo",
                remote_url="http://example.com/foo.git",
            ),
            ScratchRepository(
                name="bar",
                remote_url="http://example.com/bar.git",
            ),
            ScratchRepository(
                name="baz",
                remote_url="http://example.com/baz.git",
            ),
        ],
    )
    mock_ensure_repo.side_effect = [None, RuntimeError("bar"), None]
    with pytest.raises(RuntimeError, match="bar"):
        setup_scratch(config)

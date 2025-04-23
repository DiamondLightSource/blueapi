import os
import stat
import uuid
from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, PropertyMock, call, patch

import pytest

from blueapi.cli.scratch import (
    _fetch_installed_packages_details,
    _get_project_name_from_pyproject,
    ensure_repo,
    get_python_environment,
    scratch_install,
    setup_scratch,
)
from blueapi.config import ScratchConfig, ScratchRepository
from blueapi.service.model import PackageInfo, SourceInfo
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


def test_setup_scratch_fails_on_blueapi_included(
    directory_path_with_sgid: Path,
):
    b = ScratchRepository.model_construct(
        name="blueapi",
        remote_url="https://github.com/DiamondLightSource/blueapi.git",
    )
    config = ScratchConfig.model_construct(
        root=directory_path_with_sgid,
        required_gid=12345,
        repositories=[b],
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


@pytest.fixture
def config(directory_path_with_sgid: Path) -> ScratchConfig:
    return ScratchConfig(
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


@patch("blueapi.cli.scratch.Repo")
@patch("blueapi.cli.scratch._fetch_installed_packages_details")
@patch("blueapi.cli.scratch._get_project_name_from_pyproject")
def test_get_python_env_returns_correct_packages(
    mock_get_project_name: Mock,
    mock_fetch_installed_packages: Mock,
    mock_repo: Mock,
    directory_path_with_sgid: Path,
    config: ScratchConfig,
):
    repo_path = directory_path_with_sgid / "foo"
    repo_path.mkdir()
    mock_repo_1 = Mock()
    mock_repo_1.active_branch.name = "main"
    mock_repo_1.is_dirty.return_value = False
    mock_repo_1.remotes = [Mock(url="http://example.com/foo.git")]

    repo_path = directory_path_with_sgid / "bar"
    repo_path.mkdir()
    mock_repo_2 = Mock()
    type(mock_repo_2.active_branch).name = PropertyMock(side_effect=TypeError)
    mock_repo_2.head.commit.hexsha = "adsad23123"
    mock_repo_2.is_dirty.return_value = True
    mock_repo_2.remotes = [Mock(url="http://example.com/bar.git")]

    mock_repo.side_effect = [mock_repo_1, mock_repo_2]

    mock_get_project_name.side_effect = ["foo-package", "bar-package"]
    mock_fetch_installed_packages.return_value = [
        PackageInfo(
            name="package-01",
            version="1.0.1",
            location="/some/location",
            is_dirty=False,
        )
    ]

    response = get_python_environment(config)

    assert response.installed_packages == [
        PackageInfo(
            name="bar-package",
            version="http://example.com/bar.git @adsad23123",
            location="",
            is_dirty=True,
            source=SourceInfo.SCRATCH,
        ),
        PackageInfo(
            name="foo-package",
            version="http://example.com/foo.git @main",
            location="",
            is_dirty=False,
            source=SourceInfo.SCRATCH,
        ),
        PackageInfo(
            name="package-01",
            version="1.0.1",
            location="/some/location",
            is_dirty=False,
            source=SourceInfo.PYPI,
        ),
    ]


@patch("blueapi.cli.scratch.Repo")
@patch("blueapi.cli.scratch._fetch_installed_packages_details")
@patch("blueapi.cli.scratch._get_project_name_from_pyproject")
def test_fetch_python_env_with_identical_packages(
    mock_get_project_name: Mock,
    mock_fetch_installed_packages: Mock,
    mock_repo: Mock,
    directory_path_with_sgid: Path,
):
    repo_path = directory_path_with_sgid / "foo"
    repo_path.mkdir()
    mock_repo_instance = Mock()
    mock_repo_instance.active_branch.name = "main"
    mock_repo_instance.is_dirty.return_value = False
    mock_repo_instance.remotes = [Mock(url="http://example.com/foo.git")]

    mock_repo.return_value = mock_repo_instance

    mock_get_project_name.return_value = "foo-package"
    mock_fetch_installed_packages.return_value = [
        PackageInfo(
            name="foo-package",
            version="http://example.com/foo.git @main",
            location="/some/location",
            is_dirty=False,
            source=SourceInfo.SCRATCH,
        )
    ]
    config = ScratchConfig(
        root=directory_path_with_sgid,
        repositories=[
            ScratchRepository(
                name="foo",
                remote_url="http://example.com/foo.git",
            ),
        ],
    )
    response = get_python_environment(config)

    assert response.installed_packages == [
        PackageInfo(
            name="foo-package",
            version="http://example.com/foo.git @main",
            location="/some/location &&",
            is_dirty=False,
            source=SourceInfo.SCRATCH,
        ),
    ]


@patch("blueapi.cli.scratch.importlib.metadata.distributions")
def test_fetch_installed_packages_details_returns_correct_packages(mock_distributions):
    mock_distribution = Mock()
    mock_distribution.metadata = {"Name": "example-package"}
    mock_distribution.version = "1.0.0"
    mock_distribution.locate_file.return_value = Path("/example/location")
    mock_distributions.return_value = [mock_distribution]

    packages = _fetch_installed_packages_details()

    assert len(packages) == 1
    assert packages == [
        PackageInfo(
            name="example-package",
            version="1.0.0",
            location="/example/location",
            is_dirty=False,
        )
    ]


@patch("blueapi.cli.scratch.Repo")
@patch("blueapi.cli.scratch._fetch_installed_packages_details")
@patch("blueapi.cli.scratch._get_project_name_from_pyproject")
def test_get_python_env_filters_by_name_and_source(
    mock_get_project_name: Mock,
    mock_fetch_installed_packages: Mock,
    mock_repo: Mock,
    directory_path_with_sgid: Path,
):
    # Setup for scratch source filtering
    repo_path = directory_path_with_sgid / "foo"
    repo_path.mkdir()
    mock_repo_instance = Mock()
    mock_repo_instance.active_branch.name = "main"
    mock_repo_instance.is_dirty.return_value = False
    mock_repo_instance.remotes = [Mock(url="http://example.com/foo.git")]
    mock_repo.return_value = mock_repo_instance

    mock_get_project_name.return_value = "foo-package"
    mock_fetch_installed_packages.return_value = [
        PackageInfo(
            name="bar-package",
            version="1.0.0",
            location="/some/location",
            is_dirty=False,
            source=SourceInfo.PYPI,
        )
    ]
    config = ScratchConfig(
        root=directory_path_with_sgid,
        repositories=[
            ScratchRepository(
                name="foo",
                remote_url="http://example.com/foo.git",
            ),
        ],
    )
    # Test filtering by name
    response_by_name = get_python_environment(config, name="foo-package")
    assert response_by_name.installed_packages == [
        PackageInfo(
            name="foo-package",
            version="http://example.com/foo.git @main",
            location="",
            is_dirty=False,
            source=SourceInfo.SCRATCH,
        )
    ]

    # Test filtering by source
    response_by_source = get_python_environment(config, source=SourceInfo.SCRATCH)
    assert response_by_source.installed_packages == [
        PackageInfo(
            name="foo-package",
            version="http://example.com/foo.git @main",
            location="",
            is_dirty=False,
            source=SourceInfo.SCRATCH,
        )
    ]


@pytest.fixture
def pyproject_file(directory_path: Path) -> Generator[Path]:
    pyproject_path = directory_path / "pyproject.toml"
    with pyproject_path.open("w") as f:
        f.write(
            """
            [project]
            name = "example-project"
            """
        )
    yield pyproject_path
    os.remove(pyproject_path)


def test_get_project_name_from_pyproject_returns_name(pyproject_file: Path):
    project_name = _get_project_name_from_pyproject(pyproject_file.parent)
    assert project_name == "example-project"


def test_get_project_name_from_pyproject_returns_empty_if_no_pyproject(
    directory_path: Path,
):
    project_name = _get_project_name_from_pyproject(directory_path)
    assert project_name == ""


def test_get_project_name_from_pyproject_returns_empty_if_no_name_key(
    directory_path: Path,
):
    pyproject_path = directory_path / "pyproject.toml"
    with pyproject_path.open("w") as f:
        f.write(
            """
            [project]
            version = "1.0.0"
            """
        )
    project_name = _get_project_name_from_pyproject(directory_path)
    assert project_name == ""

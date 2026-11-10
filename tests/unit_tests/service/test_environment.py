import os
from collections.abc import Generator
from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

import pytest

from blueapi.config import ScratchConfig, ScratchRepository
from blueapi.service.environment import (
    _fetch_installed_packages_details,
    _get_project_name_from_pyproject,
    get_python_environment,
)
from blueapi.service.model import PackageInfo, SourceInfo


@pytest.fixture
def directory_path_with_sgid(tmp_path: Path) -> Path:
    return tmp_path


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


@patch("blueapi.service.environment.Repo")
@patch("blueapi.service.environment._fetch_installed_packages_details")
@patch("blueapi.service.environment._get_project_name_from_pyproject")
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


@patch("blueapi.service.environment.Repo")
@patch("blueapi.service.environment._fetch_installed_packages_details")
@patch("blueapi.service.environment._get_project_name_from_pyproject")
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


@patch("blueapi.service.environment.importlib.metadata.distributions")
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


@patch("blueapi.service.environment.Repo")
@patch("blueapi.service.environment._fetch_installed_packages_details")
@patch("blueapi.service.environment._get_project_name_from_pyproject")
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
def pyproject_file(tmp_path: Path) -> Generator[Path]:
    pyproject_path = tmp_path / "pyproject.toml"
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
    tmp_path: Path,
):
    project_name = _get_project_name_from_pyproject(tmp_path)
    assert project_name == ""


def test_get_project_name_from_pyproject_returns_empty_if_no_name_key(
    tmp_path: Path,
):
    pyproject_path = tmp_path / "pyproject.toml"
    with pyproject_path.open("w") as f:
        f.write(
            """
            [project]
            version = "1.0.0"
            """
        )
    project_name = _get_project_name_from_pyproject(tmp_path)
    assert project_name == ""

import importlib.metadata
import logging
import os
import stat
import textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import Popen

from git import Repo
from tomlkit import parse

from blueapi.config import FORBIDDEN_OWN_REMOTE_URL, ScratchConfig
from blueapi.service.model import PackageInfo, PythonEnvironmentResponse, SourceInfo
from blueapi.utils import get_owner_gid, is_sgid_set

_DEFAULT_INSTALL_TIMEOUT: float = 300.0

LOGGER = logging.getLogger(__name__)


def setup_scratch(
    config: ScratchConfig, install_timeout: float = _DEFAULT_INSTALL_TIMEOUT
) -> None:
    """
    Set up the scratch area from the config. Clone all required repositories
    if they are not cloned already. Install them into the scratch area.

    Args:
        config: Configuration for the scratch directory
        install_timeout: Timeout for installing packages
    """

    _validate_root_directory(config.root, config.required_gid)

    LOGGER.info(f"Setting up scratch area: {config.root}")

    """ fail early """
    for repo in config.repositories:
        if (
            repo.remote_url.lower() == FORBIDDEN_OWN_REMOTE_URL.lower()
            or repo.name == "blueapi"
        ):
            raise PermissionError(
                textwrap.dedent("""
        The scratch area cannot be used to clone the blueapi repository.
        That is to prevent namespace clashing with the blueapi application.
        """)
            )

    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                ensure_repo,
                repo.remote_url,
                config.root / repo.name,
                repo.target_revision,
            )
            for repo in config.repositories
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                raise RuntimeError("Failed to clone repositories") from exc

    scratch_install(
        *(config.root / repo.name for repo in config.repositories),
        timeout=install_timeout,
    )


def ensure_repo(
    remote_url: str, local_directory: Path, target_revision: str | None = None
) -> None:
    """
    Ensure that a repository is checked out for use in the scratch area.
    Clone it if it isn't.

    Args:
        remote_url: Git remote URL
        local_directory: Output path for cloning
    """

    # Set umask to DLS standard
    os.umask(stat.S_IWOTH)

    if not local_directory.exists():
        LOGGER.info(f"Cloning {remote_url}")
        Repo.clone_from(
            remote_url,
            local_directory,
            branch=target_revision,
            filter="blob:none",
        )
        LOGGER.info(f"Cloned {remote_url} -> {local_directory}")
    elif local_directory.is_dir():
        repo = Repo(local_directory)
        head = repo.head.commit
        LOGGER.info("Found %s @ %s", local_directory, head.name_rev)
        if target_revision:
            if target_revision in repo.refs:
                if repo.refs[target_revision].commit != head:
                    LOGGER.warning(
                        "Repository %s not at target revision: %r instead of %r",
                        local_directory.name,
                        head.name_rev,
                        target_revision,
                    )
            else:
                LOGGER.warning("Target revision %r not found", target_revision)
    else:
        raise KeyError(
            f"Unable to open {local_directory} as a git repository because it is not a "
            "directory"
        )


def scratch_install(*paths: Path, timeout: float = _DEFAULT_INSTALL_TIMEOUT) -> None:
    """
    Install scratch packages. Make blueapi aware of repositories checked out in
    the scratch area. Make it automatically follow code changes to those repositories
    (pending a restart). Do not install any of the packages' dependencies as they
    may conflict with each other.

    Args:
        paths: List of Paths to the checked out repositories
        timeout: Time to wait for installation subprocess
    """
    if not paths:
        return
    args = [
        "uv",
        "pip",
        "install",
        "--no-deps",
    ]
    for path in paths:
        _validate_directory(path)
        args.extend(["-e", str(path)])

    LOGGER.info("Installing packages")
    process = Popen(args)
    process.wait(timeout=timeout)
    if process.returncode != 0:
        raise RuntimeError(
            f"Failed to install packages: Exit Code: {process.returncode}"
        )


def _validate_root_directory(root_path: Path, required_gid: int | None) -> None:
    _validate_directory(root_path)

    if required_gid is not None:
        if not is_sgid_set(root_path):
            raise PermissionError(
                textwrap.dedent(f"""
            The scratch area root directory ({root_path}) needs to have the
            SGID permission bit set. This allows blueapi to clone
            repositories into it while retaining the ability for
            other users in an approved group to edit/delete them.

            See https://www.redhat.com/en/blog/suid-sgid-sticky-bit for how to
            set the SGID bit.
            """)
            )
        if get_owner_gid(root_path) != required_gid:
            raise PermissionError(
                textwrap.dedent(f"""
            The configuration requires that {root_path} be owned by the group with
            ID {required_gid}.
            You may be able to find this group's name by running the following
            in the terminal.

            getent group 1000 | cut -d: -f1

            You can transfer ownership, if you have sufficient permissions, with the
            chgrp command.
            """)
            )


def _validate_directory(path: Path) -> None:
    if not path.exists():
        raise KeyError(f"{path}: No such file or directory")
    elif path.is_file():
        raise KeyError(f"{path}: Is a file, not a directory")


def _get_project_name_from_pyproject(path: Path) -> str:
    pyproject_path = path / "pyproject.toml"
    if pyproject_path.exists():
        with pyproject_path.open("r", encoding="utf-8") as file:
            toml_data = parse(file.read())
        return toml_data.get("project", {}).get("name", "")
    return ""


def _fetch_installed_packages_details() -> list[PackageInfo]:
    installed_packages = importlib.metadata.distributions()
    return [
        PackageInfo(
            name=dist.metadata["Name"],
            version=dist.version,
            location=str(dist.locate_file("")),
            is_dirty=False,
        )
        for dist in installed_packages
    ]


def get_python_environment(
    config: ScratchConfig | None,
    name: str | None = None,
    source: SourceInfo | None = None,
) -> PythonEnvironmentResponse:
    """
    Get the Python environment. This includes all installed packages and
    the scratch packages.
    """
    scratch_packages = {}
    packages = []

    if config is None:
        python_env_response = PythonEnvironmentResponse(scratch_enabled=False)
    else:
        python_env_response = PythonEnvironmentResponse(scratch_enabled=True)
        _validate_directory(config.root)
        for repo in config.repositories:
            local_directory = config.root / repo.name
            repo = Repo(local_directory)
            try:
                branch = repo.active_branch.name
            except TypeError:
                branch = repo.head.commit.hexsha

            is_dirty = repo.is_dirty()

            version = (
                f"{repo.remotes[0].url} @{branch}"
                if repo.remotes
                else f"UNKNOWN REMOTE @{branch}"
            )
            package_name = _get_project_name_from_pyproject(local_directory)
            package_location = ""

            packages.append(
                PackageInfo(
                    name=package_name,
                    version=version,
                    location=package_location,
                    source=SourceInfo.SCRATCH,
                    is_dirty=is_dirty,
                )
            )
        scratch_packages = {p.name: p for p in packages}

    for pkg in _fetch_installed_packages_details():
        if pkg.name not in scratch_packages:
            packages.append(pkg)
        else:
            scratch_packages[pkg.name].location += f"{pkg.location} &&"

    python_env_response.installed_packages = sorted(
        packages, key=lambda pkg: pkg.name.lower()
    )
    if name:
        python_env_response.installed_packages = [
            p for p in python_env_response.installed_packages if p.name == name
        ]
    if source:
        python_env_response.installed_packages = [
            p for p in python_env_response.installed_packages if p.source == source
        ]
    return python_env_response

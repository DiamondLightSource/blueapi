import logging
import os
import stat
from pathlib import Path
from subprocess import Popen

from git import Repo

from blueapi.config import ScratchConfig

_DEFAULT_INSTALL_TIMEOUT: float = 300.0


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

    _validate_directory(config.root)

    logging.info(f"Setting up scratch area: {config.root}")

    for repo in config.repositories:
        local_directory = config.root / repo.name
        ensure_repo(repo.remote_url, local_directory)
        scratch_install(local_directory, timeout=install_timeout)


def ensure_repo(remote_url: str, local_directory: Path) -> None:
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
        logging.info(f"Cloning {remote_url}")
        Repo.clone_from(remote_url, local_directory)
        logging.info(f"Cloned {remote_url} -> {local_directory}")
    elif local_directory.is_dir():
        Repo(local_directory)
        logging.info(f"Found {local_directory}")
    else:
        raise KeyError(
            f"Unable to open {local_directory} as a git repository because "
            "it is a file"
        )


def scratch_install(path: Path, timeout: float = _DEFAULT_INSTALL_TIMEOUT) -> None:
    """
    Install a scratch package. Make blueapi aware of a repository checked out in
    the scratch area. Make it automatically follow code changes to that repository
    (pending a restart). Do not install any of the package's dependencies as they
    may conflict with each other.

    Args:
        path: Path to the checked out repository
        timeout: Time to wait for for installation subprocess
    """

    _validate_directory(path)

    # Set umask to DLS standard
    os.umask(stat.S_IWOTH)

    logging.info(f"Installing {path}")
    process = Popen(
        [
            "python",
            "-m",
            "pip",
            "install",
            "--no-deps",
            "-e",
            str(path),
        ]
    )
    process.wait(timeout=timeout)
    if process.returncode != 0:
        raise RuntimeError(f"Failed to install {path}: Exit Code: {process.returncode}")


def _validate_directory(path: Path) -> None:
    if not path.exists():
        raise KeyError(f"{path}: No such file or directory")
    elif path.is_file():
        raise KeyError(f"{path}: Is a file, not a directory")

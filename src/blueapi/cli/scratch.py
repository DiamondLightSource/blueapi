import logging
import os
from pathlib import Path
from subprocess import Popen

from git import Repo

from blueapi.config import ScratchConfig


def setup_scratch(config: ScratchConfig) -> None:
    _validate_directory(config.root)

    logging.info(f"Setting up scratch area: {config.root}")

    # Set umask to DLS standard
    os.umask(0o002)

    for repo in config.repositories:
        try:
            local_directory = config.root / repo.name
            ensure_repo(repo.remote_url, local_directory)
            scratch_install(local_directory)
        except Exception as ex:
            logging.error(
                f"An error occurred trying to set up {repo.name} in the scratch area"
            )
            logging.exception(ex)


def ensure_repo(
    remote_url: str,
    local_directory: Path,
) -> None:
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


def scratch_install(path: Path) -> None:
    _validate_directory(path)

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
    process.wait(timeout=300.0)
    if process.returncode != 0:
        raise RuntimeError(f"Failed to install {path}: Exit Code: {process.returncode}")


def _validate_directory(path: Path) -> None:
    if not path.exists():
        raise KeyError(f"{path}: No such file or directory")
    elif path.is_file():
        raise KeyError(f"{path}: Is a file, not a directory")

import logging
import os
import stat
import textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import Popen

from git import Repo

from blueapi.config import FORBIDDEN_OWN_REMOTE_URL, ScratchConfig
from blueapi.utils import get_owner_gid, is_sgid_set, validate_directory

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
        locked_repo=config.locked_repo,
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


def scratch_install(
    *paths: Path,
    timeout: float = _DEFAULT_INSTALL_TIMEOUT,
    locked_repo: Path | None = None,
) -> None:
    """
    Install scratch packages. Make blueapi aware of repositories checked out in
    the scratch area. Make it automatically follow code changes to those repositories
    (pending a restart). Do not install any of the packages' dependencies as they
    may conflict with each other.

    Args:
        paths: List of Paths to the checked out repositories
        timeout: Time to wait for installation subprocess
        locked_repo: Repository to install first from its uv.lock, if any
    """
    if not paths:
        return
    LOGGER.info("Installing packages")
    if locked_repo:
        uv_lock_path = locked_repo / "uv.lock"
        if not uv_lock_path.exists():
            raise FileNotFoundError(
                f"Installing from a uv lock file was requested, but no lock file "
                f"exists at {uv_lock_path}. Check that uv.lock exists in your "
                "repository."
            )
        # Sync the locked repo into the environment blueapi is running in.
        # --inexact stops uv removing packages not in the lock (e.g. blueapi).
        _run_install(["uv", "sync", "--locked", "--inexact", str(locked_repo)], timeout)
    # With a lock, install the rest without dependencies to keep locked versions.
    deps = ["--no-deps"] if locked_repo else []
    for path in paths:
        if locked_repo and path.resolve() == locked_repo.resolve():
            continue
        validate_directory(path)
        _run_install(["uv", "pip", "install", *deps, "-e", str(path)], timeout)


def _run_install(args: list[str], timeout: float) -> None:
    process = Popen(args)
    process.wait(timeout=timeout)
    if process.returncode != 0:
        raise RuntimeError(
            f"Failed to install packages: Exit Code: {process.returncode}"
        )


def _validate_root_directory(root_path: Path, required_gid: int | None) -> None:
    validate_directory(root_path)

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

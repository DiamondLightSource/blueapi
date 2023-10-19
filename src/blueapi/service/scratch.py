import logging
import os
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

import pkg_resources
from pydantic import Field

from blueapi.config import ScratchConfig
from blueapi.utils import BlueapiBaseModel


class PythonPackage(BlueapiBaseModel):
    name: str
    version: str
    extras: List[str] = Field(default_factory=list)


class PackageInstallation(BlueapiBaseModel):
    package: PythonPackage
    location: Path


class PipShim:
    """
    Very simple class that wraps pip commands. Can be removed if pip
    ever provides a programmatic API.
    https://github.com/pypa/pip/issues/5675
    """

    def install_editable(
        self,
        path: Path,
        extras: List[str],
    ) -> None:
        logging.debug(f"Installing {path}{extras}")
        package_arg = str(path)
        if len(extras) > 0:
            extras_fmt = ",".join(extras)
            package_source = f"{package_arg}[{extras_fmt}]"
        else:
            package_source = package_arg
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "-e",
                package_source,
            ]
        )


class ScratchManager:
    """
    Ensures editable packages are loaded from the scratch space, which is a "special"
    directory
    """

    _root_path: Path
    _auto_make_directory: bool
    _pip: PipShim

    def __init__(
        self,
        root_path: Path,
        auto_make_directory: bool,
        pip: Optional[PipShim] = None,
    ) -> None:
        self._root_path = root_path
        self._auto_make_directory = auto_make_directory
        self._pip = pip or PipShim()

    @classmethod
    def from_config(cls, config: ScratchConfig) -> "ScratchManager":
        return cls(config.path, config.auto_make_directory)

    def sync_packages(self) -> None:
        """
        Editably install all packages in the scratch directory into blueapi's Python
        environment
        """

        self._check_scratch_exists()
        directories = self._get_directories_in_scratch()
        logging.info(f"Syncing scratch packages, installing from {directories}")
        for directory in directories:
            self._pip.install_editable(directory, [])
        logging.info("Scratch packages installed")

    def _get_directories_in_scratch(self) -> Set[Path]:
        self._check_scratch_exists()
        all_files = [self._root_path / child for child in os.listdir(self._root_path)]
        return set(filter(lambda file: file.is_dir(), all_files))

    def _check_scratch_exists(self) -> None:
        if self._root_path.is_file():
            raise FileExistsError(f"{self._root_path} is not a directory")
        elif not self._root_path.exists():
            if self._auto_make_directory:
                self._root_path.mkdir(parents=True)
            else:
                raise FileNotFoundError(
                    f"Scratch directory {self._root_path} does not exist"
                )
        else:
            logging.debug("Have ensured that scratch directory exists")

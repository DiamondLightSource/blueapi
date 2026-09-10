import importlib.metadata
from pathlib import Path

from git import Repo
from tomlkit import parse

from blueapi.config import ScratchConfig
from blueapi.service.model import PackageInfo, PythonEnvironmentResponse, SourceInfo


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

# Commands for dev tooling

This page outlines useful commands for dev tooling. More information can be found in the [python-copier-template docs](https://github.com/DiamondLightSource/python-copier-template/tree/main/docs). 

The table below outlines useful commands with instructions for download on Diamond workstations.

| Command           | Installation  | Example of use|
| -------------     | ------------- | ------------- |
| `podman`          | [Dev-Guide link](https://dev-guide.diamond.ac.uk/containers/tutorials/podman/)  | `podman run ghcr.io/diamondlightsource/blueapi:latest` to pull the blueapi container from the GitHub container registry |
| `docker-compose`  | [Dev-Guide link](https://dev-guide.diamond.ac.uk/epics-containers/reference/setup/#docker-compose)  | `docker compose -f tests/system_tests/compose.yaml up -d` to spin up dummy versions of blueapi associated services |
| `uv`              | `module load uv`  | `uv run --with blueapi path/to/script.py` to run a standalone script |
| `prek`            | Run `uv run prek install` the first time the repo is cloned to set up pre-commit checks  | `uv run prek` or `uv run prek --all-files`  |
| `tox`             |  `uv tool install tox` | `tox -e tests -- tests/unit_tests/test_config.py::test_config_yaml_parsed` is an example of running a specific test and `tox -e tests` will run all unit tests|
| `just`            | `uv tool rust-just`  | `just lint` will run all pre-commit checks|

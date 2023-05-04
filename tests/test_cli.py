import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from blueapi import __version__
from blueapi.cli.cli import main


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])

    assert result.stdout == f"blueapi, version {__version__}\n"


def test_main_no_params():
    runner = CliRunner()
    result = runner.invoke(main)
    expected = (
        "Using configuration file at: src/blueapi_config.yaml. "
        + "Please invoke subcommand!\n"
    )

    assert result.stdout == expected


def test_main_with_params():
    runner = CliRunner()
    result = runner.invoke(main, ["-c", "tests/config_yaml_files/blueapi_config.yaml"])
    expected = (
        "Using configuration file at: tests/config_yaml_files/blueapi_config.yaml."
        + " Please invoke subcommand!\n"
    )

    assert result.stdout == expected

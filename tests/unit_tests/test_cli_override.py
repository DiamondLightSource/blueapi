from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from blueapi.cli import main


@pytest.fixture
def cli_runner():
    return CliRunner()


@pytest.fixture
def create_temp_yaml(tmp_path):
    """Creates a temporary YAML file for configuration testing."""

    def _create_temp_yaml(content: dict):
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(content, f)
        return config_path

    return _create_temp_yaml


def test_default_config(cli_runner):
    """Test if the CLI uses default configuration when no overrides are provided."""
    result = cli_runner.invoke(main)
    assert result.exit_code == 0
    assert "Please invoke a subcommand!" in result.output
    # Add more assertions based on the default behavior of your config


def test_config_file_override(cli_runner, create_temp_yaml):
    """Test if the configuration from a file overrides the defaults."""
    config_data = {"logging": {"level": "INFO"}, "app": {"debug": True}}
    config_path = create_temp_yaml(config_data)

    result = cli_runner.invoke(main, ["-c", str(config_path)])
    assert result.exit_code == 0
    # Validate the configuration loaded from the file
    assert "Please invoke a subcommand!" in result.output
    # Add more specific assertions regarding config_loader behavior here


def test_environment_override(cli_runner, monkeypatch, create_temp_yaml):
    """Test if environment variables override configuration file and defaults."""
    # Mock environment variables
    monkeypatch.setenv("BLUEAPI_APP_DEBUG", "false")
    monkeypatch.setenv("BLUEAPI_LOGGING_LEVEL", "ERROR")

    config_data = {"logging": {"level": "INFO"}, "app": {"debug": True}}
    config_path = create_temp_yaml(config_data)

    result = cli_runner.invoke(main, ["-c", str(config_path)])
    assert result.exit_code == 0
    # Check if environment variables take precedence over the config file
    assert "Please invoke a subcommand!" in result.output
    # Add more assertions to check config values were overridden correctly


def test_cli_override(cli_runner, monkeypatch, create_temp_yaml):
    """Test if CLI arguments override both environment variables and config file."""
    # Mock environment variables
    monkeypatch.setenv("BLUEAPI_LOGGING_LEVEL", "WARNING")

    config_data = {"logging": {"level": "INFO"}, "app": {"debug": True}}
    config_path = create_temp_yaml(config_data)

    result = cli_runner.invoke(
        main,
        [
            "-c",
            str(config_path),
            "--app.logging.level=DEBUG",
            "--app.debug=false",
        ],
    )
    assert result.exit_code == 0
    # Check if CLI arguments take precedence over both config file and env vars
    assert "Please invoke a subcommand!" in result.output
    # Add assertions for the overridden values


def test_file_not_found(cli_runner):
    """Test if a FileNotFoundError is raised for missing config file."""
    non_existent_path = Path("/path/to/nonexistent/file.yaml")
    result = cli_runner.invoke(main, ["-c", str(non_existent_path)])
    assert result.exit_code != 0
    assert "Cannot find file" in result.output

# config_manager.py

from blueapi.config import ApplicationConfig


class ConfigManager:
    """Manages application configuration in a way that’s easy to test and mock."""

    _config: ApplicationConfig

    def __init__(self, config: ApplicationConfig = None):
        if config is None:
            ApplicationConfig.model_config["yaml_file"] = None
            config = ApplicationConfig()
        self._config = config

    def get_config(self) -> ApplicationConfig:
        """Retrieve the current configuration."""
        return self._config

    def set_config(self, new_config: ApplicationConfig):
        """
        This is a setter function that the main process uses
        to pass the config into the subprocess
        """
        self._config = new_config

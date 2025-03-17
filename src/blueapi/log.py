import logging

from dodal.log import LOGGER as dodal_logger
from dodal.log import (
    get_graylog_configuration,
    integrate_bluesky_and_ophyd_logging,
    set_up_graylog_handler,
    set_up_stream_handler,
)

from blueapi.config import LoggingConfig


def do_default_logging_setup(dev_mode=False) -> None:
    """Configure package level logger for blueapi.

    Configures logger with name `blueapi`. Any logger within the blueapi package
    instantiated with `logging.getLogger(__name__)` will propogate to this logger
    assuming the default `logger.propagate` is True, and no filters block it.

    Args:
        dev_mode: bool which sets graylog config to localhost:5555
    """
    logging_config = LoggingConfig()

    LOGGER = logging.getLogger("blueapi")
    LOGGER.setLevel(logging_config.level)
    LOGGER.parent = dodal_logger
    set_up_stream_handler(LOGGER)
    set_up_graylog_handler(
        LOGGER, *get_graylog_configuration(dev_mode, logging_config.graylog_port)
    )
    integrate_bluesky_and_ophyd_logging(dodal_logger)

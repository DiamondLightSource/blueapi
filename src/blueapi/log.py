import logging
from typing import Optional

from dodal.log import LOGGER as dodal_logger
from dodal.log import (
    DodalLogHandlers,
    get_graylog_configuration,
    set_up_graylog_handler,
    set_up_stream_handler,
)

from blueapi.config import LoggingConfig

logging_config = LoggingConfig()

LOGGER = logging.getLogger("blueapi")
LOGGER.setLevel(logging_config.level)
LOGGER.parent = dodal_logger

__logger_handlers: DodalLogHandlers | None = None


def do_default_logging_setup(dev_mode=False):
    handlers = {}
    handlers["stream_handler"] = set_up_stream_handler(LOGGER)
    handlers["graylog_handler"] = set_up_graylog_handler(
        LOGGER, *get_graylog_configuration(dev_mode, logging_config.graylog_port)
    )
    global __logger_handlers
    __logger_handlers = handlers

import logging

import colorlog
from bluesky.log import logger as bluesky_logger
from dodal.log import LOGGER as dodal_logger
from graypy import GELFTCPHandler
from ophyd.log import logger as ophyd_logger

from blueapi.config import LoggingConfig

DEFAULT_GRAYLOG_PORT = 12231

# Temporarily duplicated https://github.com/bluesky/ophyd-async/issues/550
DEFAULT_FORMAT = (
    "%(log_color)s[%(levelname)1.1s %(asctime)s.%(msecs)03d "
    "%(module)s:%(lineno)d] %(message)s"
)

DEFAULT_DATE_FORMAT = "%y%m%d %H:%M:%S"

DEFAULT_LOG_COLORS = {
    "DEBUG": "cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "red,bg_white",
}


class ColoredFormatterWithDeviceName(colorlog.ColoredFormatter):
    def format(self, record):
        message = super().format(record)
        if device_name := getattr(record, "ophyd_async_device_name", None):
            message = f"[{device_name}]{message}"
        return message


DEFAULT_FORMATTER = ColoredFormatterWithDeviceName(
    fmt=DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT, log_colors=DEFAULT_LOG_COLORS
)


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


def integrate_bluesky_and_ophyd_logging(parent_logger: logging.Logger):
    # Temporarily duplicated https://github.com/bluesky/ophyd-async/issues/550
    ophyd_async_logger = logging.getLogger("ophyd_async")
    for logger in [ophyd_logger, bluesky_logger, ophyd_async_logger]:
        logger.parent = parent_logger
        logger.setLevel(logging.DEBUG)


def get_graylog_configuration(
    dev_mode: bool, graylog_port: int | None = None
) -> tuple[str, int]:
    """Get the host and port for the graylog handler.

    If running in dev mode, this switches to localhost. Otherwise it publishes to the
    DLS graylog.

    Returns:
        (host, port): A tuple of the relevant host and port for graylog.
    """
    if dev_mode:
        return "localhost", 5555
    else:
        return "graylog-log-target.diamond.ac.uk", graylog_port or DEFAULT_GRAYLOG_PORT


def _add_handler(logger: logging.Logger, handler: logging.Handler):
    print(f"adding handler {handler} to logger {logger}, at level: {handler.level}")
    handler.setFormatter(DEFAULT_FORMATTER)
    logger.addHandler(handler)


def set_up_stream_handler(logger: logging.Logger):
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    _add_handler(logger, stream_handler)
    return stream_handler


def set_up_graylog_handler(logger: logging.Logger, host: str, port: int):
    """Set up a graylog handler for the logger, at "INFO" level, with the at the
    specified address and host. get_graylog_configuration() can provide these values
    for prod and dev respectively.
    """
    graylog_handler = GELFTCPHandler(host, port)
    graylog_handler.setLevel(logging.INFO)
    _add_handler(logger, graylog_handler)
    return graylog_handler

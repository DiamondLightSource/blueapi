import logging
import os

from bluesky.log import logger as bluesky_logger
from dodal.log import LOGGER as dodal_logger
from graypy import GELFTCPHandler
from ophyd.log import logger as ophyd_logger

from blueapi.config import LoggingConfig


class BeamlineFilter(logging.Filter):
    beamline: str | None = os.environ.get("BEAMLINE")

    def filter(self, record):
        record.beamline = self.beamline if self.beamline else "dev"
        return True


class InstrumentFilter(logging.Filter):
    instrument: str | None = os.environ.get("BEAMLINE")

    def filter(self, record):
        record.instrument = self.instrument if self.instrument else "dev"
        return True


def do_default_logging_setup(logging_config: LoggingConfig) -> None:
    """Configure package level logger for blueapi.

    Configures logger with name `blueapi`. Any logger within the blueapi package
    instantiated with `logging.getLogger(__name__)` will propogate to this logger
    assuming the default `logger.propagate` is True, and no filters block it.

    Args:
        dev_mode: bool which sets graylog config to localhost:5555
    """

    logger = logging.getLogger("blueapi")

    logger.setLevel(logging_config.level)

    handlers = []

    stream_handler = set_up_stream_handler(logger, logging_config)
    handlers.append(stream_handler)

    if logging_config.graylog_export_enabled:
        graylog_handler = set_up_graylog_handler(logger, logging_config)
        handlers.append(graylog_handler)

    integrate_bluesky_and_ophyd_logging(logger)

    for handler in handlers:
        handler.addFilter(BeamlineFilter())
        handler.addFilter(InstrumentFilter())


def integrate_bluesky_and_ophyd_logging(parent_logger: logging.Logger):
    # Temporarily duplicated https://github.com/bluesky/ophyd-async/issues/550
    ophyd_async_logger = logging.getLogger("ophyd_async")
    for logger in [ophyd_logger, bluesky_logger, ophyd_async_logger, dodal_logger]:
        logger.parent = parent_logger
        logger.setLevel(logging.DEBUG)


def _add_handler(logger: logging.Logger, handler: logging.Handler):
    print(f"adding handler {handler} to logger {logger}, at level: {handler.level}")
    logger.addHandler(handler)


def set_up_stream_handler(logger: logging.Logger, logging_config: LoggingConfig):
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging_config.level)
    _add_handler(logger, stream_handler)
    return stream_handler


def set_up_graylog_handler(logger: logging.Logger, logging_config: LoggingConfig):
    graylog_handler = GELFTCPHandler(
        logging_config.graylog_host, logging_config.graylog_port
    )
    graylog_handler.setLevel(logging_config.level)
    _add_handler(logger, graylog_handler)
    return graylog_handler

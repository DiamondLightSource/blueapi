import logging
import os

from graypy import GELFTCPHandler

from blueapi.config import LoggingConfig


class BeamlineTagFilter(logging.Filter):
    beamline: str | None = os.environ.get("BEAMLINE")

    def filter(self, record):
        record.beamline = self.beamline if self.beamline else "dev"
        return True


class InstrumentTagFilter(logging.Filter):
    instrument: str | None = os.environ.get("BEAMLINE")

    def filter(self, record):
        record.instrument = self.instrument if self.instrument else "dev"
        return True


def setup_logging(logging_config: LoggingConfig) -> None:
    """Configure package level logger for blueapi.

    Configures logger with name `blueapi`. Any logger within the blueapi package
    instantiated with `logging.getLogger(__name__)` will propogate to this logger
    assuming the default `logger.propagate` is True, and no filters block it.

    Args:
        logging_config: LoggingConfig
    """

    logger = logging.getLogger()

    logger.setLevel(logging_config.level)

    handlers = []

    stream_handler = set_up_stream_handler(logger, logging_config)
    handlers.append(stream_handler)

    if logging_config.graylog_export_enabled:
        graylog_handler = set_up_graylog_handler(logger, logging_config)
        handlers.append(graylog_handler)

    filters = [
        BeamlineTagFilter(),
        InstrumentTagFilter(),
    ]

    add_all_filters_to_all_handlers(handlers, filters)


def set_up_stream_handler(logger: logging.Logger, logging_config: LoggingConfig):
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging_config.level)
    logger.addHandler(stream_handler)
    return stream_handler


def set_up_graylog_handler(logger: logging.Logger, logging_config: LoggingConfig):
    if logging_config.logging_dev_mode:
        graylog_handler = GELFTCPHandler("localhost", 5555)
    else:
        graylog_handler = GELFTCPHandler(
            logging_config.graylog_host, logging_config.graylog_port
        )
    graylog_handler.setLevel(logging_config.level)
    logger.addHandler(graylog_handler)
    return graylog_handler


def add_all_filters_to_all_handlers(
    handlers: list[logging.Handler], filters: list[logging.Filter]
):
    for handler in handlers:
        for filter in filters:
            handler.addFilter(filter)

import logging
import os

from graypy import GELFTCPHandler

from blueapi.config import LoggingConfig


class InstrumentTagFilter(logging.Filter):
    """Filter to attach instrument and beamline attributes to LogRecords.

    Attaches attributes `instrument` and `beamline` to all LogRecords that are passed
    through. Value is taken from `BEAMLINE` env var, defaulting to `dev`.
    """

    instrument: str = os.environ.get("BEAMLINE", os.environ.get("INSTRUMENT", "dev"))

    def filter(self, record: logging.LogRecord) -> bool:
        record.instrument = self.instrument
        record.beamline = self.instrument
        return True


def set_up_logging(logging_config: LoggingConfig) -> None:
    """Configure root level logger for blueapi.

    Configures root logger. Any other logger will propogate to this logger assuming the
    default `logger.propagate` is True, and no filters block it.

    Args:
        logging_config: LoggingConfig
    """

    logger = logging.getLogger()

    logger.setLevel(logging_config.level)

    filters: list[logging.Filter] = [
        InstrumentTagFilter(),
    ]

    set_up_stream_handler(logger, logging_config, filters)

    if logging_config.graylog.enabled:
        set_up_graylog_handler(logger, logging_config, filters)


def set_up_stream_handler(
    logger: logging.Logger, logging_config: LoggingConfig, filters: list[logging.Filter]
) -> logging.StreamHandler:
    """Creates and configures StreamHandler, then attaches to logger.

    Args:
        logger: Logger to attach handler to
        logging_config: LoggingConfig
    """
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging_config.level)

    for filter in filters:
        stream_handler.addFilter(filter)

    logger.addHandler(stream_handler)
    return stream_handler


def set_up_graylog_handler(
    logger: logging.Logger, logging_config: LoggingConfig, filters: list[logging.Filter]
) -> GELFTCPHandler:
    """Creates and configures GELFTCPHandler, then attaches to logger.

    Args:
        logger: Logger to attach handler to
        logging_config: LoggingConfig
    """
    graylog_handler = GELFTCPHandler(
        logging_config.graylog.host, logging_config.graylog.port
    )
    graylog_handler.setLevel(logging_config.level)

    for filter in filters:
        graylog_handler.addFilter(filter)

    logger.addHandler(graylog_handler)
    return graylog_handler

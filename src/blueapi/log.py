import enum
import logging
import os
from contextlib import contextmanager
from copy import copy

import click
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


class PlanTagFilter(logging.Filter):
    """Filter to attach name of plan as an attribute to LogRecords.

    Attaches the attribute `plan_name` to all LogRecords that are passed through.
    """

    def __init__(self, plan_name: str):
        self.plan_name = plan_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.plan_name = self.plan_name
        return True


@contextmanager
def plan_tag_filter_context(plan_name: str, logger: logging.Logger):
    """Context manager that attaches and removes `PlanTagFilter` to a given logger.

    Creates an instance of PlanTagFilter and attaches it to the given logger for the
    duration of the context. On exit the filter is removed.

        Args:
            plan_name: str name of plan being executed
            logger: logging.Logger to attach filter to
    """
    filter = PlanTagFilter(plan_name)
    try:
        logger.addFilter(filter)
        yield
    finally:
        logger.removeFilter(filter)


def set_up_logging(logging_config: LoggingConfig) -> None:
    """Configure root level logger for blueapi.

    Configures root logger. Any other logger will propagate to this logger assuming the
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

    formatter = ColorFormatter("%(asctime)s %(levelname)s %(message)s")
    stream_handler.setFormatter(formatter)

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
    assert logging_config.graylog.url.host is not None, "Graylog URL missing host"
    assert logging_config.graylog.url.port is not None, "Graylog URL missing port"
    graylog_handler = GELFTCPHandler(
        logging_config.graylog.url.host,
        logging_config.graylog.url.port,
    )
    graylog_handler.setLevel(logging_config.level)

    for filter in filters:
        graylog_handler.addFilter(filter)

    logger.addHandler(graylog_handler)
    return graylog_handler


class IBMColorBlindSafeColors(enum.Enum):
    ultramarine = (100, 143, 255)
    indigo = (120, 94, 240)
    magenta = (220, 38, 127)
    orange = (254, 97, 0)
    gold = (255, 176, 0)


class ColorFormatter(logging.Formatter):
    """Colors level_name of log using IBM color blind safe palette."""

    def _level_colour(self, level_no: int) -> tuple[int, int, int] | None:
        match level_no:
            case logging.DEBUG:
                return IBMColorBlindSafeColors.ultramarine.value
            case logging.INFO:
                return IBMColorBlindSafeColors.indigo.value
            case logging.WARNING:
                return IBMColorBlindSafeColors.gold.value
            case logging.ERROR:
                return IBMColorBlindSafeColors.magenta.value
            case logging.CRITICAL:
                return IBMColorBlindSafeColors.orange.value
            case _:
                return None

    def formatMessage(self, record: logging.LogRecord) -> str:  # noqa: N802
        # Copy record to avoid modifying for other handlers etc.
        recordcopy = copy(record)
        recordcopy.levelname = click.style(
            f"{recordcopy.levelname:>8}", fg=self._level_colour(recordcopy.levelno)
        )
        return super().formatMessage(recordcopy)

import logging
from unittest.mock import patch

import pytest
from bluesky.log import logger as bluesky_logger
from dodal.log import LOGGER as dodal_logger
from ophyd.log import logger as ophyd_logger

from blueapi.config import GraylogConfig, LoggingConfig
from blueapi.log import set_up_logging


def clear_all_loggers_and_handlers(logger):
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()

    # pytest adds handlers to root logger. Hopefully this doesn't break anything...
    if logger.parent:
        clear_all_loggers_and_handlers(logger.parent)


LOGGER_NAMES = ["", "blueapi", "blueapi.test"]


@pytest.fixture(params=LOGGER_NAMES)
def logger_with_graylog(request):
    logger = logging.getLogger(request.param)
    graylog_config = GraylogConfig(enabled=True)
    set_up_logging(LoggingConfig(graylog=graylog_config))
    yield logger
    clear_all_loggers_and_handlers(logger)


@pytest.fixture(params=LOGGER_NAMES)
def logger_without_graylog(request):
    logger = logging.getLogger(request.param)
    graylog_config = GraylogConfig(enabled=False)
    set_up_logging(LoggingConfig(graylog=graylog_config))
    yield logger
    clear_all_loggers_and_handlers(logger)


@pytest.fixture
def logger(logger_with_graylog):
    return logger_with_graylog


@pytest.fixture
def mock_stream_handler_emit():
    with patch("blueapi.log.logging.StreamHandler.emit") as stream_handler_emit:
        # stream_handler_emit.reset_mock()
        yield stream_handler_emit


@pytest.fixture
def mock_graylog_emit():
    with patch("blueapi.log.GELFTCPHandler.emit") as graylog_emit:
        yield graylog_emit


MOCK_HANDLER_EMIT_STRINGS = [
    "blueapi.log.logging.StreamHandler.emit",
    "blueapi.log.GELFTCPHandler.emit",
]


@pytest.fixture(params=MOCK_HANDLER_EMIT_STRINGS)
def mock_handler_emit(request):
    with patch(request.param) as mock_emit:
        yield mock_emit


def test_loggers_emits_to_all_handlers(logger, mock_handler_emit):
    mock_handler_emit.assert_not_called()
    logger.info("FOO")
    mock_handler_emit.assert_called()


def test_logger_does_not_emit_to_graylog(logger_without_graylog, mock_graylog_emit):
    mock_graylog_emit.assert_not_called()
    logger_without_graylog.info("FOO")
    mock_graylog_emit.assert_not_called()


def test_messages_are_tagged_with_beamline(logger, mock_handler_emit):
    logger.info("FOO")
    assert mock_handler_emit.call_args[0][0].beamline == "dev"


def test_messages_are_tagged_with_instrument(logger, mock_handler_emit):
    logger.info("FOO")
    assert mock_handler_emit.call_args[0][0].instrument == "dev"


# Temporarily duplicated https://github.com/bluesky/ophyd-async/issues/550
@pytest.mark.parametrize(
    "library_logger",
    [bluesky_logger, dodal_logger, ophyd_logger, logging.getLogger("ophyd_async")],
)
def test_library_logger_intergrations(logger, library_logger, mock_handler_emit):
    mock_handler_emit.assert_not_called()
    library_logger.info("FOO")
    mock_handler_emit.assert_called()

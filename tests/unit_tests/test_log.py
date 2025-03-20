import logging
from unittest.mock import patch

import pytest

from blueapi.config import LoggingConfig
from blueapi.log import do_default_logging_setup


def clear_all_loggers_and_handlers(logger):
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()

    if logger.parent and logger.parent != logging.RootLogger:
        clear_all_loggers_and_handlers(logger.parent)


LOGGER_NAMES = ["blueapi", "blueapi.test"]


@pytest.fixture(params=LOGGER_NAMES)
def logger_with_graylog(request):
    logger = logging.getLogger(request.param)
    do_default_logging_setup(LoggingConfig(graylog_export_enabled=True))
    yield logger
    clear_all_loggers_and_handlers(logger)


@pytest.fixture(params=LOGGER_NAMES)
def logger_without_graylog(request):
    logger = logging.getLogger(request.param)
    do_default_logging_setup(LoggingConfig(graylog_export_enabled=False))
    yield logger
    clear_all_loggers_and_handlers(logger)


@pytest.fixture
def logger(logger_with_graylog):
    return logger_with_graylog


@pytest.fixture
def mock_stream_handler_emit():
    with patch("blueapi.log.logging.StreamHandler.emit") as stream_handler_emit:
        stream_handler_emit.reset_mock()
        yield stream_handler_emit


@pytest.fixture
def mock_graylog_emit():
    with patch("blueapi.log.GELFTCPHandler.emit") as graylog_emit:
        yield graylog_emit


@pytest.fixture
def mock_handlers_emits(mock_stream_handler_emit, mock_graylog_emit):
    return [
        mock_stream_handler_emit,
        mock_graylog_emit,
    ]


@pytest.fixture
def mock_logger_config() -> LoggingConfig:
    return LoggingConfig(graylog_export_enabled=False)


def test_logger_emits_to_graylog(logger_with_graylog, mock_graylog_emit):
    mock_graylog_emit.assert_not_called()
    logger_with_graylog.info("FOO")
    mock_graylog_emit.assert_called_once()


def test_logger_does_not_emit_to_graylog(logger_without_graylog, mock_graylog_emit):
    mock_graylog_emit.assert_not_called()
    logger_without_graylog.info("FOO")
    mock_graylog_emit.assert_not_called()


def test_stream_handler_emits(logger, mock_stream_handler_emit):
    logger.info("FOO")
    mock_stream_handler_emit.assert_called()


def test_messages_are_tagged_with_beamline(logger, mock_stream_handler_emit):
    logger.info("FOO")
    assert mock_stream_handler_emit.call_args[0][0].beamline == "dev"


def test_messages_are_tagged_with_instrument(logger, mock_stream_handler_emit):
    logger.info("FOO")
    assert mock_stream_handler_emit.call_args[0][0].instrument == "dev"


def test_dodal_logger_intergrated():
    raise NotImplementedError()


def test_ophyd_logger_intergrated():
    raise NotImplementedError()


def test_ophyd_async_logger_intergrated():
    raise NotImplementedError()


def test_bluesky_logger_intergrated():
    raise NotImplementedError()

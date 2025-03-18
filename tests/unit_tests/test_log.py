import logging
from unittest.mock import patch

import pytest

from blueapi.config import LoggingConfig
from blueapi.log import do_default_logging_setup

LOGGER = logging.getLogger("blueapi")


@pytest.fixture
def mock_graylog_emit():
    with patch("dodal.log.GELFTCPHandler.emit") as graylog_emit:
        graylog_emit.reset_mock()
        yield graylog_emit


@pytest.fixture
def mock_logger_config():
    with patch("blueapi.log.LoggingConfig") as mock_logging_config:
        logger_config = LoggingConfig()

        logger_config.graylog_export_enabled = False

        mock_logging_config.return_value = logger_config

        yield logger_config


@pytest.fixture
def mock_stream_handler_emit():
    with patch("dodal.log.StreamHandler.emit") as stream_handler_emit:
        stream_handler_emit.reset_mock()
        yield stream_handler_emit


def test_logger_emits_to_graylog(mock_graylog_emit):
    do_default_logging_setup(dev_mode=True)
    LOGGER.info("FOO")
    mock_graylog_emit.assert_called()


def test_logger_does_not_emit_to_graylog(mock_graylog_emit, mock_logger_config):
    do_default_logging_setup(dev_mode=False)
    LOGGER.info("FOO")
    mock_graylog_emit.assert_not_called()


def test_stream_handler_emits(mock_stream_handler_emit):
    do_default_logging_setup(dev_mode=True)
    LOGGER.info("FOO")
    mock_stream_handler_emit.assert_called()


def test_messages_are_tagged_with_beamline(mock_stream_handler_emit):
    do_default_logging_setup(dev_mode=True)
    LOGGER.info("FOO")
    assert mock_stream_handler_emit.call_args[0][0].beamline == "dev"


def test_messages_are_tagged_with_instrument(mock_stream_handler_emit):
    do_default_logging_setup(dev_mode=True)
    LOGGER.info("FOO")
    assert mock_stream_handler_emit.call_args[0][0].instrument == "dev"


def test_messages_are_tagged_with_plan_name(mock_stream_handler_emit):
    raise NotImplementedError()

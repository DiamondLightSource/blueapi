from unittest.mock import patch

import pytest

from blueapi.log import LOGGER, do_default_logging_setup


@pytest.fixture
def mock_graylog_emit():
    with patch("dodal.log.GELFTCPHandler.emit") as graylog_emit:
        graylog_emit.reset_mock()
        yield graylog_emit


@pytest.fixture
def mock_stream_handler_emit():
    with patch("dodal.log.StreamHandler.emit") as stream_handler_emit:
        stream_handler_emit.reset_mock()
        yield stream_handler_emit


def test_logger_emits(mock_graylog_emit):
    # def test_logger_emits(mock_handlers):
    do_default_logging_setup(dev_mode=True)
    LOGGER.info("FOO")
    mock_graylog_emit.assert_called()

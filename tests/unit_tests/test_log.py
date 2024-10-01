import logging
from unittest.mock import patch

import pytest

from blueapi.log import LOGGER, do_default_logging_setup

# do_default_logging_setup(dev_mode=True)
LOGGER.info("BAR")


@pytest.fixture
def mock_loggers():
    with patch("dodal.log.GELFTCPHandler.emit") as graylog_emit:
        graylog_emit.reset_mock()
        yield graylog_emit


def test_logger_emits(mock_loggers):
    LOGGER.info("FOO")
    mock_loggers.assert_called()

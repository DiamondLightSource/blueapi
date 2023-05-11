import pytest
from mock import Mock, patch

from blueapi.service.handler import (
    Handler,
    get_handler,
    setup_handler,
    teardown_handler,
)


@patch("blueapi.service.handler.Handler")
def test_get_handler_raises_before_setup_hadler_called(
    mock_handler: Mock, handler: Handler
):
    mock_handler.side_effect = Mock(return_value=handler)

    with pytest.raises(ValueError):
        handler = get_handler()

    setup_handler()
    handler = get_handler()
    assert handler

    teardown_handler()

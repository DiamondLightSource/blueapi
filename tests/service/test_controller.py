import pytest
from mock import Mock, patch

from blueapi.config import ApplicationConfig
from blueapi.service.controller import (
    BlueskyController,
    get_controller,
    initialize_controller,
    teardown_controller,
)


@patch("blueapi.service.controller.BlueskyController")
def test_get_controller_raises_before_setup_controller_called(
    mock_controller: Mock, controller: BlueskyController
):
    mock_controller.side_effect = Mock(return_value=controller)

    with pytest.raises(ValueError):
        controller = get_controller()

    initialize_controller(ApplicationConfig())
    controller = get_controller()
    assert controller

    teardown_controller()


def test_teardown_controller_does_nothing_if_setup_controller_not_called():
    assert teardown_controller() is None

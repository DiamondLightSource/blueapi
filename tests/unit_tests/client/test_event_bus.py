from unittest.mock import ANY, Mock

import pytest
from bluesky_stomp.messaging import StompClient

from blueapi.client.event_bus import BlueskyStreamingError, EventBusClient


@pytest.fixture
def mock_template() -> StompClient:
    return Mock(spec=StompClient)


@pytest.fixture
def events(mock_template: StompClient) -> EventBusClient:
    return EventBusClient(app=mock_template)


def test_context_manager_connects_and_disconnects(
    events: EventBusClient,
    mock_template: Mock,
):
    mock_template.connect.assert_not_called()
    mock_template.disconnect.assert_not_called()

    with events:
        mock_template.connect.assert_called_once()
        mock_template.disconnect.assert_not_called()

    mock_template.disconnect.assert_called_once()


def test_client_subscribes_to_all_events(
    events: EventBusClient,
    mock_template: Mock,
):
    on_event = Mock
    with events:
        events.subscribe_to_all_events(on_event=on_event)  # type: ignore
    mock_template.subscribe.assert_called_once_with(ANY, on_event)


def test_client_raises_streaming_error_on_subscribe_failure(
    events: EventBusClient,
    mock_template: Mock,
):
    mock_template.subscribe.side_effect = RuntimeError("Foo")
    on_event = Mock
    with events:
        with pytest.raises(
            BlueskyStreamingError,
            match="Unable to subscribe to messages from blueapi",
        ):
            events.subscribe_to_all_events(on_event=on_event)  # type: ignore

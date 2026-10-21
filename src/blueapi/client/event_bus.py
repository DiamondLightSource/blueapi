from collections.abc import Callable

from bluesky_stomp.messaging import MessageContext, StompClient
from bluesky_stomp.models import MessageTopic

from blueapi.core import DataEvent
from blueapi.worker import ProgressEvent, WorkerEvent


class BlueskyStreamingError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


AnyEvent = WorkerEvent | ProgressEvent | DataEvent
OnAnyEvent = Callable[[AnyEvent], None]


class EventBusClient:
    app: StompClient

    def __init__(self, app: StompClient) -> None:
        self.app = app
        self._subscription_ids: list[str] = []

    def __enter__(self) -> None:
        self.app.connect()

    def __exit__(self, exc_type, exc_value, exc_traceback) -> None:
        while len(self._subscription_ids) > 0:
            self.app.unsubscribe(self._subscription_ids.pop())
        self.app.disconnect()

    def subscribe_to_all_events(
        self,
        on_event: Callable[[AnyEvent, MessageContext], None],
    ) -> None:
        try:
            subscription_id = self.app.subscribe(
                MessageTopic(name="public.worker.event"),
                on_event,
            )
            self._subscription_ids.append(subscription_id)
        except Exception as err:
            raise BlueskyStreamingError(
                "Unable to subscribe to messages from blueapi"
            ) from err

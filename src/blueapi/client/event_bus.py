from collections.abc import Callable

from blueapi.core import DataEvent
from blueapi.messaging import MessageContext, MessagingTemplate
from blueapi.worker import ProgressEvent, WorkerEvent


class BlueskyStreamingError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


AnyEvent = WorkerEvent | ProgressEvent | DataEvent
OnAnyEvent = Callable[[AnyEvent], None]


class EventBusClient:
    app: MessagingTemplate

    def __init__(self, app: MessagingTemplate) -> None:
        self.app = app

    def __enter__(self) -> None:
        self.app.connect()

    def __exit__(self, exc_type, exc_value, exc_traceback) -> None:
        self.app.disconnect()

    def subscribe_to_all_events(
        self,
        on_event: Callable[[MessageContext, AnyEvent], None],
    ) -> None:
        try:
            self.app.subscribe(
                self.app.destinations.topic("public.worker.event"),
                on_event,
            )
        except Exception as err:
            raise BlueskyStreamingError(
                "Unable to subscribe to messages from blueapi"
            ) from err

import threading
from collections.abc import Callable

from blueapi.core import DataEvent
from blueapi.messaging import MessageContext, MessagingTemplate
from blueapi.worker import ProgressEvent, WorkerEvent


class BlueskyRemoteError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


AnyEvent = WorkerEvent | ProgressEvent | DataEvent
OnAnyEvent = Callable[[AnyEvent], None]


class EventBusClient:
    app: MessagingTemplate
    complete: threading.Event
    timed_out: bool | None

    def __init__(self, app: MessagingTemplate) -> None:
        self.app = app
        self.complete = threading.Event()
        self.timed_out = None

    def __enter__(self) -> None:
        self.app.connect()

    def __exit__(self, exc_type, exc_value, exc_traceback) -> None:
        self.app.disconnect()

    def subscribe_to_all_events(
        self,
        on_event: Callable[[MessageContext, AnyEvent], None],
    ) -> None:
        self.app.subscribe(
            self.app.destinations.topic("public.worker.event"),
            on_event,
        )

    def wait_for_complete(self, timeout: float | None = None) -> None:
        self.timed_out = not self.complete.wait(timeout=timeout)

        self.complete.clear()

import threading
from collections.abc import Callable

from bluesky.callbacks.best_effort import BestEffortCallback

from blueapi.core import DataEvent
from blueapi.messaging import MessageContext, MessagingTemplate
from blueapi.worker import ProgressEvent, WorkerEvent

from .updates import CliEventRenderer


class BlueskyRemoteError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


_Event = WorkerEvent | ProgressEvent | DataEvent


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

    def subscribe_to_topics(
        self,
        correlation_id: str,
        on_event: Callable[[WorkerEvent], None] | None = None,
    ) -> None:
        """Run callbacks on events/progress events with a given correlation id."""

        progress_bar = CliEventRenderer(correlation_id)
        callback = BestEffortCallback()

        def on_event_wrapper(
            ctx: MessageContext,
            event: _Event,
        ) -> None:
            if isinstance(event, WorkerEvent):
                if (on_event is not None) and (ctx.correlation_id == correlation_id):
                    on_event(event)

                if (event.is_complete()) and (ctx.correlation_id == correlation_id):
                    self.complete.set()
            elif isinstance(event, ProgressEvent):
                progress_bar.on_progress_event(event)
            elif isinstance(event, DataEvent):
                callback(event.name, event.doc)

        self.subscribe_to_all_events(on_event_wrapper)

    def subscribe_to_all_events(
        self,
        on_event: Callable[[MessageContext, _Event], None],
    ) -> None:
        self.app.subscribe(
            self.app.destinations.topic("public.worker.event"),
            on_event,
        )

    def wait_for_complete(self, timeout: float | None = None) -> None:
        self.timed_out = not self.complete.wait(timeout=timeout)

        self.complete.clear()

import threading
from typing import Callable, Optional, Union

from bluesky.callbacks.best_effort import BestEffortCallback

from blueapi.core import DataEvent
from blueapi.messaging import MessageContext, MessagingTemplate
from blueapi.worker import ProgressEvent, WorkerEvent

from .updates import CliEventRenderer


class BlueskyRemoteError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class AmqClient:
    app: MessagingTemplate
    complete: threading.Event
    timed_out: Optional[bool]

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
        on_event: Optional[Callable[[WorkerEvent], None]] = None,
    ) -> None:
        """Run callbacks on events/progress events with a given correlation id."""

        progress_bar = CliEventRenderer(correlation_id)
        callback = BestEffortCallback()

        def on_event_wrapper(
            ctx: MessageContext, event: Union[WorkerEvent, ProgressEvent, DataEvent]
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

        self.app.subscribe(
            self.app.destinations.topic("public.worker.event"),
            on_event_wrapper,
        )

    def wait_for_complete(self, timeout: Optional[float] = None) -> None:
        self.timed_out = not self.complete.wait(timeout=timeout)

        self.complete.clear()

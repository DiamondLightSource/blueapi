import threading
import time
from typing import Callable, Optional, TypeVar

from blueapi.messaging import MessageContext, MessagingTemplate
from blueapi.worker import ProgressEvent, WorkerEvent

T = TypeVar("T")


class BlueskyRemoteError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class AmqClient:
    app: MessagingTemplate
    complete: threading.Event

    def __init__(self, app: MessagingTemplate) -> None:
        self.app = app
        self.complete = threading.Event()

    def subscribe_to_topics(
        self,
        corr_id: str,
        on_event: Optional[Callable[[WorkerEvent], None]] = None,
        on_progress_event: Optional[Callable[[ProgressEvent], None]] = None,
    ) -> None:
        """Run callbacks on events/progress events with a given correlation id."""

        self.app.connect()

        def on_event_wrapper(ctx: MessageContext, event: WorkerEvent) -> None:
            print(
                f"correlation_id: {ctx.correlation_id}, corr_id: {corr_id}, "
                + f"event.is_complete: {event.is_complete()}"
            )
            if (on_event is not None) and (ctx.correlation_id == corr_id):
                on_event(event)

            if (event.is_complete()) and (ctx.correlation_id == corr_id):
                self.complete.set()
                if event.is_error():
                    raise BlueskyRemoteError(str(event.errors) or "Unknown error")

        def on_progress_event_wrapper(
            ctx: MessageContext, event: ProgressEvent
        ) -> None:
            if on_progress_event is not None:
                on_progress_event(event)

        self.app.subscribe(
            self.app.destinations.topic("public.worker.event"),
            on_event_wrapper,
        )
        self.app.subscribe(
            self.app.destinations.topic("public.worker.event.progress"),
            on_progress_event_wrapper,
        )

    def wait_for_complete(
        self,
    ) -> None:
        while not self.complete.is_set():
            time.sleep(0.1)

        self.complete.clear()

import threading
import time
from typing import Callable, Optional

from blueapi.messaging import MessageContext, MessagingTemplate
from blueapi.worker import WorkerEvent


class BlueskyRemoteError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class AmqClient:
    app: MessagingTemplate
    complete: threading.Event

    def __init__(self, app: MessagingTemplate) -> None:
        self.app = app
        self.complete = threading.Event()

    def __enter__(self) -> None:
        self.app.connect()

    def __exit__(self, exc_type, exc_value, exc_traceback) -> None:
        self.app.disconnect()

    def subscribe_to_topics(
        self,
        task_id: str,
        on_event: Optional[Callable[[WorkerEvent], None]] = None,
    ) -> None:
        """Run callbacks on events/progress events with a given correlation id."""

        def on_event_wrapper(ctx: MessageContext, event: WorkerEvent) -> None:
            if (on_event is not None) and (ctx.task_id == task_id):
                on_event(event)

            if (event.is_complete()) and (ctx.task_id == task_id):
                self.complete.set()

        self.app.subscribe(
            self.app.destinations.topic("public.worker.event"),
            on_event_wrapper,
        )

    def wait_for_complete(self, timeout: Optional[float] = None) -> None:
        begin_time = time.time()
        timedout = False
        while not self.complete.is_set():
            current_time = time.time()
            if (timeout is not None) and ((current_time - begin_time) > timeout):
                timedout = True
                break

        if timedout:
            raise BlueskyRemoteError(
                f"task took longer than {timeout}s to finish. Terminating."
            )

        self.complete.clear()

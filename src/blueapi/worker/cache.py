import logging
import queue
from threading import Thread

from blueapi.core.bluesky_types import DataEvent
from blueapi.core.event import EventPublisher
from blueapi.worker.event import ProgressEvent, WorkerEvent

LOGGER = logging.getLogger(__name__)

AnyEvent = WorkerEvent | DataEvent | ProgressEvent


class EventCache:
    cache: queue.Queue[tuple[str | None, AnyEvent]]

    worker_events: EventPublisher[WorkerEvent]
    progress_events: EventPublisher[ProgressEvent]
    data_events: EventPublisher[DataEvent]

    _running: Thread

    def __init__(self) -> None:
        self.cache = queue.Queue()
        self.worker_events = EventPublisher()
        self.progress_events = EventPublisher()
        self.data_events = EventPublisher()

    def start(self) -> None:
        t = Thread(target=self._cycle, daemon=True)
        self._running = t
        self._running.start()

    def push(self, task_id: str | None, event: AnyEvent) -> None:
        LOGGER.debug("Adding event to cache: %s", event)
        self.cache.put((task_id, event), block=True)

    def _cycle(self) -> None:
        q = self.cache

        while True:
            try:
                (_id, event) = q.get(block=True)
                LOGGER.debug("Publishing event %s", event)

                match event:
                    case WorkerEvent():
                        self.worker_events.publish(event)
                    case ProgressEvent():
                        self.progress_events.publish(event)
                    case DataEvent():
                        self.data_events.publish(event)
                q.task_done()
            except queue.Empty:
                pass
            except queue.ShutDown:
                return

    def shutdown(self, immediate: bool = False) -> None:
        LOGGER.debug("Shutting down, processing event cache")
        self.cache.shutdown(immediate)
        self._running.join()

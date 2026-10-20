import logging
from collections import deque
from threading import Event, Thread

from blueapi.core.bluesky_types import DataEvent
from blueapi.core.event import EventPublisher
from blueapi.worker.event import ProgressEvent, WorkerEvent

LOGGER = logging.getLogger(__name__)

AnyEvent = WorkerEvent | DataEvent | ProgressEvent


class EventCache:
    cache: deque[tuple[str | None, AnyEvent]]

    _shutdown: Event
    _broadcast_thread: Thread

    worker_events: EventPublisher[WorkerEvent]
    progress_events: EventPublisher[ProgressEvent]
    data_events: EventPublisher[DataEvent]

    def __init__(self) -> None:
        self.cache = deque()

        self.worker_events = EventPublisher()
        self.progress_events = EventPublisher()
        self.data_events = EventPublisher()

        self._shutdown = Event()
        broadcast = Thread(target=self._cycle, daemon=True)
        self._broadcast_thread = broadcast
        self._broadcast_thread.start()

    def push(self, task_id: str | None, event: AnyEvent) -> None:
        self.cache.append((task_id, event))

    def _cycle(self) -> None:
        while not self._shutdown.is_set():
            while len(self.cache) > 0:
                (_id, event) = self.cache.popleft()

                match event:
                    case WorkerEvent():
                        self.worker_events.publish(event)
                    case ProgressEvent():
                        self.progress_events.publish(event)
                    case DataEvent():
                        self.data_events.publish(event)

    def shutdown(self) -> None:
        """If the cache isn't clear, dump it to disk."""

        self._shutdown.set()
        if len(self.cache) != 0:
            # dump it somewhere
            LOGGER.info("Cache not cleared, dumping to disk")
            raise NotImplementedError("Sort outbackups")

    def recover() -> None:
        """
        Before dealing with anythin new, if there is an old cache
        that got saved, publish those first.

        """
        ...

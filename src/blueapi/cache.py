from collections import deque
from threading import Event, Thread

from blueapi.core.bluesky_types import DataEvent
from blueapi.core.event import EventPublisher


class DocCache:
    cache: deque[tuple[str, DataEvent]]

    _broadcast_thread: Thread
    _shutdown: Event

    publisher: EventPublisher[DataEvent]

    def __init__(self) -> None:
        self.cache = deque()

        self._shutdown = Event()

        broadcast = Thread(target=self._cycle, daemon=True)
        self._broadcast_thread = broadcast
        self._broadcast_thread.start()

        self.publisher = EventPublisher()

    def push(self, event: DataEvent) -> None:
        self.cache.append((event.task_id, event))

    def _cycle(self) -> None:
        while not self._shutdown.is_set():
            while len(self.cache) > 0:
                (_id, doc) = self.cache.pop()
                self.publisher.publish(doc)

    def shutdown(self) -> None:
        """If the cache isn't clear, dump it to disk."""

        self._shutdown.set()

        if len(self.cache) != 0:
            # dump it somewhere
            ...

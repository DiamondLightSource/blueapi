import itertools
import threading
from abc import ABC, abstractmethod
from typing import Callable, Dict, Generic, TypeVar

E = TypeVar("E")
S = TypeVar("S")


class EventStream(ABC, Generic[E, S]):
    @abstractmethod
    def subscribe(self, __callback: Callable[[E], None]) -> S:
        ...

    @abstractmethod
    def unsubscribe(self, __subscription: S) -> None:
        ...

    @abstractmethod
    def unsubscribe_all(self) -> None:
        ...


class EventPublisher(EventStream[E, int]):
    _subscriptions: Dict[int, Callable[[E], None]]
    _count: itertools.count

    def __init__(self) -> None:
        self._subscriptions = {}
        self._count = itertools.count()

    def subscribe(self, callback: Callable[[E], None]) -> int:
        sub_id = next(self._count)
        self._subscriptions[sub_id] = callback
        return sub_id

    def unsubscribe(self, subscription: int) -> None:
        del self._subscriptions[subscription]

    def unsubscribe_all(self) -> None:
        self._subscriptions = {}

    def publish(self, event: E) -> None:
        for callback in self._subscriptions.values():
            callback(event)

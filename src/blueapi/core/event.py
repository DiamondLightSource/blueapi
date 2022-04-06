from abc import ABC, abstractmethod
from typing import AsyncIterable, Callable, Dict, Generic, List, Mapping, TypeVar

E = TypeVar("E")
S = TypeVar("S")


class EventStreamBase(ABC, Generic[E, S]):
    @abstractmethod
    def subscribe(self, __callback: Callable[[E], None]) -> S:
        ...

    @abstractmethod
    def unsubscribe(self, __subscription: S) -> None:
        ...

    @abstractmethod
    def unsubscribe_all(self) -> None:
        ...


class EventStream(EventStreamBase[E, int]):
    _subscriptions: Dict[int, Callable[[E], None]]
    _count: int

    def subscribe(self, callback: Callable[[E], None]) -> int:
        self._count += 1
        self._subscriptions[self._count] = callback
        return self._count

    def unsubscribe(self, subscription: int) -> None:
        del self._subscriptions[subscription]

    def unsubscribe_all(self) -> None:
        self._subscriptions = {}

    def notify(self, value: E) -> None:
        for callback in self._subscriptions.values():
            callback(value)

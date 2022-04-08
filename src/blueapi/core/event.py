import asyncio
from abc import ABC, abstractmethod
from typing import Awaitable, Callable, Dict, Generic, Optional, TypeVar

import janus

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


class AsyncEventStreamBase(ABC, Generic[E, S]):
    @abstractmethod
    def subscribe(self, __callback: Callable[[E], Awaitable[None]]) -> S:
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


class AsyncEventStreamWrapper(AsyncEventStreamBase[E, S]):
    _wrapped: EventStreamBase[E, S]
    _loop: asyncio.AbstractEventLoop

    def __init__(
        self,
        wrapped: EventStreamBase[E, S],
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        if loop is None:
            loop = asyncio.get_event_loop()
        self._wrapped = wrapped
        self._loop = loop

    def subscribe(self, callback: Callable[[E], Awaitable[None]]) -> S:
        def sync_callback(value: E) -> None:
            asyncio.run_coroutine_threadsafe(callback(value), self._loop)

        return self._wrapped.subscribe(sync_callback)

    def unsubscribe(self, subscription: S) -> None:
        return self._wrapped.unsubscribe(subscription)

    def unsubscribe_all(self) -> None:
        return self._wrapped.unsubscribe_all()

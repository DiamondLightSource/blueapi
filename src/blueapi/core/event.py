import itertools
from abc import ABC, abstractmethod
from typing import Callable, Dict, Generic, TypeVar

#: Event type
E = TypeVar("E")

#: Subscription token type
S = TypeVar("S")


class EventStream(ABC, Generic[E, S]):
    """
    Generic representation of the Observable pattern
    """

    @abstractmethod
    def subscribe(self, __callback: Callable[[E], None]) -> S:
        """
        Subscribe to new events with a callback

        Args:
            __callback (Callable[[E], None]): What to do with each event

        Returns:
            S: A unique token representing the subscription
        """

        ...

    @abstractmethod
    def unsubscribe(self, __subscription: S) -> None:
        """
        Stop propagating events to a particular subscription

        Args:
            __subscription (S): The token identifying the subscription
        """

        ...

    @abstractmethod
    def unsubscribe_all(self) -> None:
        """
        Unsubscribe from all subscriptions
        """

        ...


class EventPublisher(EventStream[E, int]):
    """
    Simple Observable that can be fed values to publish
    """

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
        """
        Publish a new event to all subscribers

        Args:
            event (E): The event to publish
        """

        for callback in self._subscriptions.values():
            callback(event)

import itertools
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Generic, TypeVar

#: Event type
E = TypeVar("E")

#: Subscription token type
S = TypeVar("S")


class EventStream(ABC, Generic[E, S]):
    """
    Generic representation of the Observable pattern
    """

    @abstractmethod
    def subscribe(self, __callback: Callable[[E, str | None], None]) -> S:
        """
        Subscribe to new events with a callback

        Args:
            __callback: What to do with each event, optionally takes a correlation id

        Returns:
            S: A unique token representing the subscription
        """

    @abstractmethod
    def unsubscribe(self, __subscription: S) -> None:
        """
        Stop propagating events to a particular subscription

        Args:
            __subscription (S): The token identifying the subscription
        """

    @abstractmethod
    def unsubscribe_all(self) -> None:
        """
        Unsubscribe from all subscriptions
        """


class EventPublisher(EventStream[E, int]):
    """
    Simple Observable that can be fed values to publish
    """

    _subscriptions: dict[int, Callable[[E, str | None], None]]
    _count: itertools.count

    def __init__(self) -> None:
        self._subscriptions = {}
        self._count = itertools.count()

    def subscribe(self, callback: Callable[[E, str | None], None]) -> int:
        sub_id = next(self._count)
        self._subscriptions[sub_id] = callback
        return sub_id

    def unsubscribe(self, subscription: int) -> None:
        del self._subscriptions[subscription]

    def unsubscribe_all(self) -> None:
        self._subscriptions = {}

    def publish(self, event: E, correlation_id: str | None = None) -> None:
        """
        Publish a new event to all subscribers

        Args:
            event: The event to publish
            correlation_id: An optional ID that may be used to correlate this
                event with other events
        """

        for callback in list(self._subscriptions.values()):
            callback(event, correlation_id)

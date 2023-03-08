from abc import ABC, abstractmethod
from concurrent.futures import Future
from typing import Any, Callable, Optional, Type

from .context import MessageContext

MessageListener = Callable[[MessageContext, Any], None]


class DestinationProvider(ABC):
    """
    Class that provides destinations for specific types of message bus.
    Implementation may be eager or lazy.
    """

    @abstractmethod
    def default(self, name: str) -> str:
        """
        A default type of destination with a given name.
        For example, the provider could default to using queues if no
        preference is specified.

        Args:
            name (str): The name of the destination

        Returns:
            str: Identifier for the destination
        """

    @abstractmethod
    def queue(self, name: str) -> str:
        """
        A queue with the given name

        Args:
            name (str): Name of the queue

        Returns:
            str: Identifier for the queue
        """

    @abstractmethod
    def topic(self, name: str) -> str:
        """
        A topic with the given name

        Args:
            name (str): Name of the topic

        Returns:
            str: Identifier for the topic
        """

    @abstractmethod
    def temporary_queue(self, name: str) -> str:
        """
        A temporary queue with the given name

        Args:
            name (str): Name of the queue

        Returns:
            str: Identifier for the queue
        """


class MessagingTemplate(ABC):
    """
    Class meant for quickly building message-based applications.
    Includes helpers for asyncronous production/consumption and
    synchronous send/recieve model
    """

    @property
    @abstractmethod
    def destinations(self) -> DestinationProvider:
        """
        Get a destination provider that can create destination
        identifiers for this particular template

        Returns:
            DestinationProvider: Destination provider
        """

    def send_and_recieve(
        self,
        destination: str,
        obj: Any,
        reply_type: Type = str,
        correlation_id: Optional[str] = None,
    ) -> Future:
        """
        Send a message expecting a single reply.

        Args:
            destination (str): Destination to send the message
            obj (Any): Message to send, must be serializable
            reply_type (Type, optional): Expected type of reply, used
                                         in deserialization. Defaults to str.

        Returns:
            Future: Future representing the reply
        """

        future: Future = Future()

        def callback(_: MessageContext, reply: Any) -> None:
            future.set_result(reply)

        callback.__annotations__["reply"] = reply_type
        self.send(destination, obj, callback, correlation_id)
        return future

    @abstractmethod
    def send(
        self,
        __destination: str,
        __obj: Any,
        __on_reply: Optional[MessageListener] = None,
        __correlation_id: Optional[str] = None,
    ) -> None:
        """
        Send a message to a destination

        Args:
            destination (str): Destination to send the message
            obj (Any): Message to send, must be serializable
            __on_reply (Optional[MessageListener], optional): Callback function for
                                                              a reply. Defaults to None.
        """

    def listener(self, destination: str):
        """
        Decorator for subscribing to a topic:

        @my_app.listener("my-destination")
        def callback(context: MessageContext, message: ???) -> None:
            ...

        Args:
            destination (str): Destination to subscribe to
        """

        def decorator(callback: MessageListener) -> MessageListener:
            self.subscribe(destination, callback)
            return callback

        return decorator

    @abstractmethod
    def subscribe(
        self,
        __destination: str,
        __callback: MessageListener,
    ) -> None:
        """
        Subscribe to messages from a particular destination. Requires
        a callback of the form:

        def callback(context: MessageContext, message: ???) -> None:
            ...

        The type annotation of the message will be inspected and used in
        deserialilization.

        Args:
            __destination (str): Destination to subscribe to
            __callback (MessageListener): What to do with each message
        """

    @abstractmethod
    def connect(self) -> None:
        """
        Connect the app to transport
        """

    @abstractmethod
    def disconnect(self) -> None:
        """
        Disconnect the app from transport
        """

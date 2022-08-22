from abc import ABC, abstractmethod
from concurrent.futures import Future
from typing import Any, Callable, Optional, Type

from .context import MessageContext

MessageListener = Callable[[MessageContext, Any], None]


class MessagingTemplate(ABC):
    """
    Class meant for quickly building message-based applications.
    Includes helpers for asyncronous production/consumption and
    synchronous send/recieve model
    """

    def send_and_recieve(
        self,
        destination: str,
        obj: Any,
        reply_type: Type = str,
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
        self.send(destination, obj, callback)
        return future

    @abstractmethod
    def send(
        self,
        __destination: str,
        __obj: Any,
        __on_reply: Optional[MessageListener] = None,
    ) -> None:
        """
        Send a message to a destination

        Args:
            destination (str): Destination to send the message
            obj (Any): Message to send, must be serializable
            __on_reply (Optional[MessageListener], optional): Callback function for
                                                              a reply. Defaults to None.
        """

        ...

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

        ...

    @abstractmethod
    def connect(self) -> None:
        """
        Connect the app to transport
        """
        ...

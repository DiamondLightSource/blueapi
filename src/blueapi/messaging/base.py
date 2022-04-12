from abc import ABC, abstractmethod
from concurrent.futures import Future
from typing import Any, Callable, Optional, Type, TypeVar

from .context import MessageContext

MessageListener = Callable[[MessageContext, Any], None]

T = TypeVar("T")


class MessageSession(ABC):
    @property
    @abstractmethod
    def destination(self) -> str:
        ...

    @property
    def reply_destination(self) -> Optional[str]:
        ...

    @property
    def raw_message(self) -> str:
        ...

    @abstractmethod
    def reply(self, __obj: Any) -> None:
        ...

    @abstractmethod
    def subscribe(self, __callback: MessageListener) -> None:
        ...


class Message(ABC):
    @abstractmethod
    def add_reply_callback(self, __callback: MessageListener) -> None:
        ...

    @abstractmethod
    def send(self) -> None:
        ...


class MessagingApp(ABC):
    @abstractmethod
    def send(
        self,
        __destination: str,
        __obj: Any,
        __on_reply: Optional[MessageListener] = None,
    ) -> None:
        ...

    def send_and_recieve(
        self,
        destination: str,
        obj: Any,
        reply_type: Type = str,
        timeout: Optional[float] = None,
    ) -> Future:
        future: Future = Future()

        def callback(_: MessageContext, reply: Any) -> None:
            future.set_result(reply)

        callback.__annotations__["reply"] = reply_type
        self.send(destination, obj, callback)
        return future.result(timeout)

    @abstractmethod
    def subscribe(
        self,
        __destination: str,
        __callback: MessageListener,
    ) -> None:
        ...

    @abstractmethod
    def connect(self) -> None:
        ...

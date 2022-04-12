from abc import ABC, abstractmethod
from concurrent.futures import Future
from typing import Any, Callable, Optional, Type

from .context import MessageContext

MessageListener = Callable[[MessageContext, Any], None]


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
        return future

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

import inspect
import json
import logging
import uuid
from concurrent.futures import Future
from ctypes import Union
from re import S
from typing import Any, Callable, Dict, Optional, Type, TypeVar

import stomp
from apischema import deserialize, serialize
from stomp.utils import Frame

from blueapi.core import schema_for_func
from blueapi.utils import handle_all_exceptions

LOGGER = logging.getLogger(__name__)


class MessageContext:
    _app: "MessagingApp"
    _reply_destination: Optional[str]

    def __init__(
        self, app: "MessagingApp", reply_destination: Optional[str] = None
    ) -> None:
        self._app = app
        self._reply_destination = reply_destination

    @property
    def can_reply(self) -> bool:
        return self._reply_destination is not None

    def reply(self, obj: Any) -> None:
        if self._reply_destination is not None:
            self._app.send(self._reply_destination, obj)
        else:
            raise KeyError("This message cannot be replied to")


MessageListener = Callable[[MessageContext, Any], None]

T = TypeVar("T")


class MessagingApp:
    _conn: stomp.Connection
    _sub_num: int
    _listener: stomp.ConnectionListener
    _subscriptions: Dict[str, Callable[[Frame], None]]

    def __init__(self, host: str = "127.0.0.1", port: int = 61613) -> None:
        self._conn = stomp.Connection([(host, port)])
        self._sub_num = 0
        self._listener = stomp.ConnectionListener()

        self._listener.on_message = self._on_message
        self._conn.set_listener("", self._listener)

        self._subscriptions = {}

    def send_and_recieve(
        self,
        destination: str,
        obj: Any,
        reply_type: Optional[Type[T]] = None,
        timeout: Optional[float] = None,
    ) -> T:
        future: Future = Future()

        def on_reply(_: MessageContext, message: Any) -> None:
            future.set_result(message)

        self.send(destination, obj, on_reply, reply_type=reply_type)
        return future.result(timeout)

    def send(
        self,
        destination: str,
        obj: Any,
        on_reply: Optional[MessageListener] = None,
        reply_type: Optional[Type[T]] = None,
    ) -> None:
        return self._send_str(destination, json.dumps(serialize(obj)), on_reply)

    def _send_str(
        self,
        destination: str,
        message: str,
        on_reply: Optional[MessageListener] = None,
        reply_type: Optional[Type[T]] = None,
    ) -> None:
        LOGGER.info(f"SENDING {message} to {destination}")

        headers: Dict[str, Any] = {}
        if on_reply is not None:
            reply_queue_name = f"temp.{uuid.uuid1()}"
            headers = {**headers, "reply-to": reply_queue_name}
            self.subscribe(on_reply, reply_queue_name, obj_type=reply_type)
        self._conn.send(headers=headers, body=message, destination=destination)

    def subscribe(
        self,
        callback: MessageListener,
        destination: str,
        obj_type: Optional[Type] = None,
    ) -> None:
        LOGGER.info(f"New subscription to {destination}")

        if obj_type is None:
            obj_type = _determine_deserialization_type(callback, default=str)

        def wrapper(frame: Frame) -> None:
            as_dict = json.loads(frame.body)
            value = deserialize(obj_type, as_dict)

            context = MessageContext(self, frame.headers.get("reply-to"))
            callback(context, value)

        # sub_id = str(uuid.uuid1())
        self._sub_num += 1
        sub_id = str(self._sub_num)

        self._subscriptions[sub_id] = wrapper
        self._conn.subscribe(destination=destination, id=sub_id, ack="auto")

    def connect(self) -> None:
        self._conn.connect()

    def await_terminated(self) -> None:
        self._conn.heartbeat_terminate_event.wait()

    @handle_all_exceptions
    def _on_message(self, frame: Frame) -> None:
        LOGGER.info(f"Recieved {frame}")
        sub_id = frame.headers.get("subscription")
        callback = self._subscriptions.get(sub_id)
        if callback is not None:
            callback(frame)
        else:
            LOGGER.warn(f"No subscription active for id: {sub_id}")


def _determine_deserialization_type(
    listener: MessageListener, default: Type = str
) -> Type:

    _, message = inspect.signature(listener).parameters.values()
    a_type = message.annotation
    if a_type is not inspect.Parameter.empty:
        return a_type
    else:
        return default

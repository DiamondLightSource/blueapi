import json
import logging
import uuid
from dataclasses import dataclass
from threading import Thread, Event
from typing import Any, Dict, Optional, Callable

import pika
from apischema import deserialize, serialize
from blueapi.config import AMQPConfig
from pika.channel import Channel
from pika.frame import Method
from pika.spec import BasicProperties, Basic

from .base import DestinationProvider, MessageListener, MessagingTemplate
from .context import MessageContext
from .utils import determine_deserialization_type

LOGGER = logging.getLogger(__name__)


def _ready(ready: Event) -> Callable[[Method], None]:
    def channel_ready(_: Method):
        ready.set()
    return channel_ready


def _begin_consume(ch: Channel, destination: str, wrapper, ready: Event):
    def queue_declared(_: Method):
        ch.basic_consume(queue=destination, on_message_callback=wrapper, callback=_ready(ready))
    return queue_declared


@dataclass
class Subscription:
    destination: str
    callback: MessageListener


class AMQPDestinationProvider(DestinationProvider):  # TODO: Return dict?
    """
    Destination provider for amqp, stateless so just
    uses naming conventions
    """

    def queue(self, name: str) -> str:  # May be empty, must not start with "amq."
        return name

    def topic(
        self, name: str
    ) -> str:  # Must be a series of words separated by dots for.example.this
        return name

    def temporary_queue(
        self, name: str
    ) -> str:  # May pass "" to get a uniquely named queue, channel remembers name
        return name

    default = queue


class AMQPMessagingTemplate(MessagingTemplate):
    """
    MessagingTemplate that uses the amqp protocol, meant for use
    with RabbitMQ.
    """

    _params: pika.ConnectionParameters
    _connection: pika.BaseConnection
    _subscriptions: Dict[str, Subscription]
    _connection_ready: Event
    _shutting_down: Event
    _shutdown: Event
    _thread: Thread

    # Stateless implementation means attribute can be static
    _destination_provider: DestinationProvider = AMQPDestinationProvider()

    def __init__(self, parameters: pika.ConnectionParameters) -> None:
        self._params = parameters
        self._subscriptions = {}
        self._connection_ready = Event()
        self._shutting_down = Event()
        self._shutdown = Event()

    @classmethod
    def autoconfigured(cls, config: AMQPConfig) -> MessagingTemplate:
        return cls(
            pika.ConnectionParameters(
                host=config.host,
                port=config.port,
                credentials=pika.credentials.PlainCredentials(
                    username=config.userid, password=config.password
                ),
                virtual_host=config.virtual_host,
            )
        )

    @property
    def destinations(self) -> DestinationProvider:
        return self._destination_provider

    def send(
        self,
        destination: str,
        obj: Any,
        on_reply: Optional[MessageListener] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        self._send_str(
            destination, json.dumps(serialize(obj)), on_reply, correlation_id
        )

    def _send_str(
        self,
        destination: str,
        message: str,
        on_reply: Optional[MessageListener] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        LOGGER.info(f"SENDING {message} to {destination}")

        correlation_id = correlation_id or str(
            uuid.uuid4()
        )  # rabbitmq python tutorial recommends handling callbacks on queue-per-consumer rather than queue-per-callback
        published: Event = Event()  # Do not return from method until message has been published
        callback_queue: str = str(uuid.uuid4()) if on_reply is not None else None

        ready: Event = Event()
        ch: Channel = self._connection.channel(on_open_callback=_ready(ready))
        ready.wait()

        def send_message(_: Method):
            ch.basic_publish(
                properties=pika.BasicProperties(
                    reply_to=callback_queue,
                    correlation_id=correlation_id,
                    content_type="application/json",
                ),
                exchange="",
                routing_key=destination,
                body=message.encode("utf-8"),
            )
            LOGGER.debug(f"Sent to queue {destination}")
            published.set()
            ch.close()

        if on_reply is not None:
            obj_type = determine_deserialization_type(on_reply, default=str)
            cbready: Event = Event()
            cb: Channel = self._connection.channel(on_open_callback=_ready(cbready))
            cbready.wait()

            def wrapper(
                channel: Channel,
                deliver: Basic.Deliver,
                properties: BasicProperties,
                body: bytes,
            ) -> None:
                if properties.correlation_id == correlation_id:
                    value = json.loads(body.decode("utf-8"))
                    if obj_type is not str:
                        value = deserialize(obj_type, value)

                    context = MessageContext(
                        destination=callback_queue,
                        reply_destination=properties.reply_to,
                        correlation_id=properties.correlation_id,
                    )
                    on_reply(context, value)  # TODO: Thread?
                    channel.basic_ack(deliver.delivery_tag)

            subscribed: Event = Event()
            cb.queue_declare(queue=callback_queue, callback=_begin_consume(cb, callback_queue, wrapper, subscribed), auto_delete=True)
            subscribed.wait()

        ch.queue_declare(queue=destination, callback=send_message)
        published.wait()

    def subscribe(self, destination: str, callback: MessageListener) -> None:
        LOGGER.debug(f"New subscription to {destination}")
        subscription_id = str(uuid.uuid4())
        self._subscriptions[subscription_id] = Subscription(destination, callback)
        if (
            self._connection is not None
            and self._connection.is_open
        ):
            self._subscribe(subscription_id)

    def _subscribe(self, subscription_id: str) -> None:
        subscription = self._subscriptions.get(subscription_id)
        LOGGER.debug(
            f"Subscribing to {subscription.destination} with {subscription.callback}"
        )

        obj_type = determine_deserialization_type(subscription.callback, default=str)
        ready: Event = Event()
        cb: Channel = self._connection.channel(on_open_callback=_ready(ready))
        ready.wait()

        def wrapper(
            channel: Channel, deliver: Basic.Deliver, properties: BasicProperties, body: bytes
        ) -> None:
            value = json.loads(body.decode("utf-8"))
            if obj_type is not str:
                value = deserialize(obj_type, value)

            context = MessageContext(
                destination=subscription.destination,  # TODO: Get from headers?
                reply_destination=properties.reply_to,
                correlation_id=properties.correlation_id,
            )
            subscription.callback(context, value)  # TODO: Thread?
            channel.basic_ack(deliver.delivery_tag)

        subscribed: Event = Event()
        cb.queue_declare(queue=subscription.destination, callback=_begin_consume(cb, subscription.destination, wrapper, subscribed))
        subscribed.wait()

    def disconnect(self) -> None:
        LOGGER.info(f"Disconnecting from {self._params._host}")
        if self._connection:
            self._connection_ready.clear()
            if self._shutting_down.is_set():
                self._shutdown.wait()
                return
            self._shutting_down.set()
            if self._connection.is_open:
                self._connection.close()  # TODO: Thread? Event?
            self._shutdown.wait()
            self._shutting_down.clear()
            self._shutdown.clear()

    def connect(self) -> None:
        LOGGER.info(f"Connecting to {self._params._host}")

        def begin_subscriptions(_: pika.BaseConnection):
            for subscription in self._subscriptions:
                self._subscribe(subscription)
            self._connection_ready.set()
            LOGGER.info(f"Subscriptions opened on {self._params._host}, Connection ready")

        def close_connection(
            _: pika.BaseConnection, exception
        ):  # TODO: Check for exception
            self._shutdown.set()

        self._connection = pika.SelectConnection(
            parameters=self._params,
            on_open_callback=begin_subscriptions,
            on_close_callback=close_connection,
        )

        self._thread = Thread(target=self._connection.ioloop.start, daemon=True)
        self._thread.start()
        while not self._connection_ready.wait(timeout=5):
            LOGGER.warning(
                f"Not connected to {self._params._host} after 5 seconds!"
            )  # TODO: loop twice then error then quit?

import json
import logging
import uuid
from dataclasses import dataclass
from threading import Thread, Event
from typing import Any, Dict, Optional

import pika
from apischema import deserialize, serialize
from blueapi.config import AMQPConfig
from pika.channel import Channel
from pika.spec import BasicProperties, Basic

from .base import DestinationProvider, MessageListener, MessagingTemplate
from .context import MessageContext
from .utils import determine_deserialization_type

LOGGER = logging.getLogger(__name__)


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

    def topic(self, name: str) -> str:  # Must be a series of words separated by dots for.example.this
        return name

    def temporary_queue(self, name: str) -> str:  # May pass "" to get a uniquely named queue, channel remembers name
        return name

    default = queue


class AMQPMessagingTemplate(MessagingTemplate):
    """
    MessagingTemplate that uses the amqp protocol, meant for use
    with RabbitMQ.
    """

    _params: pika.ConnectionParameters
    _connection: pika.BaseConnection
    _channel: pika.channel.Channel
    _callback_queue: str  # A queue, exclusively for this consumer, for callback messages
    _subscriptions: Dict[str, Subscription]
    _connection_ready: Event
    _shutting_down: Event
    _shutdown: Event
    _thread: Thread

    # Stateless implementation means attribute can be static
    _destination_provider: DestinationProvider = AMQPDestinationProvider()

    def __init__(
            self,
            parameters: pika.ConnectionParameters
    ) -> None:
        self._params = parameters
        self._callback_queue = str(uuid.uuid4())
        self._subscriptions = {}
        self._connection_ready = Event()
        self._shutting_down = Event()
        self._shutdown = Event()

    @classmethod
    def autoconfigured(cls, config: AMQPConfig) -> MessagingTemplate:
        return cls(
            pika.ConnectionParameters(host=config.host,
                                      port=config.port,
                                      credentials=pika.credentials.PlainCredentials(
                                          username=config.userid,
                                          password=config.password
                                      ),
                                      virtual_host=config.virtual_host)
        )

    @property
    def destinations(self) -> DestinationProvider:
        return self._destination_provider

    def send(
            self, destination: str, obj: Any, on_reply: Optional[MessageListener] = None,
            correlation_id: Optional[str] = None,
    ) -> None:
        self._send_str(
            destination,
            json.dumps(serialize(obj)),
            on_reply,
            correlation_id
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
            uuid.uuid4())  # rabbitmq python tutorial recommends handling callbacks thusly on queue-per-consumer rather than queue-per-callback

        def send_message(_):
            self._channel.basic_publish(
                properties=pika.BasicProperties(
                    reply_to=self._callback_queue,
                    correlation_id=correlation_id,
                    content_type="application/json"
                ),
                exchange='',
                routing_key=destination,
                body=message.encode('utf-8'),
            )

        if on_reply:
            obj_type = determine_deserialization_type(on_reply, default=str)

            def wrapper(channel: Channel, method: Basic.Deliver, properties: BasicProperties, body: bytes) -> None:
                if properties.correlation_id == correlation_id:
                    value = json.loads(body.decode('utf-8'))
                    if obj_type is not str:
                        value = deserialize(obj_type, value)

                    context = MessageContext(
                        destination=self._callback_queue,  # TODO: Allow for changing callback_queue name if exclusive?
                        reply_destination=properties.reply_to,
                        correlation_id=properties.correlation_id
                    )
                    on_reply(context, value)

            self._channel.basic_consume(queue=self._callback_queue, on_message_callback=wrapper)

        self._channel.queue_declare(queue=destination, callback=send_message)

    def subscribe(self, destination: str, callback: MessageListener) -> None:

        LOGGER.debug(f"New subscription to {destination}")
        subscription_id = str(uuid.uuid4())
        self._subscriptions[subscription_id] = Subscription(destination, callback)
        if self._connection is not None and self._connection.is_open and self._channel is not None and self._channel.is_open:
            self._subscribe(subscription_id)

    def _subscribe(self, subscription_id: str) -> None:
        subscription = self._subscriptions.get(subscription_id)
        LOGGER.debug(f"Subscribing to {subscription.destination} with {subscription.callback}")

        obj_type = determine_deserialization_type(subscription.callback, default=str)

        def wrapper(_: Channel, __: Basic.Deliver, properties: BasicProperties, body: bytes) -> None:
            value = json.loads(body.decode('utf-8'))
            if obj_type is not str:
                value = deserialize(obj_type, value)

            context = MessageContext(
                destination=subscription.destination,  # TODO: Get from headers?
                reply_destination=properties.reply_to,
                correlation_id=properties.correlation_id
            )
            subscription.callback(context, value)

        self._channel.queue_declare(queue=subscription.destination)

        self._channel.basic_consume(queue=subscription.destination,
                                    on_message_callback=wrapper)  # TODO: callback for ACK

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

        def declare_channel(_: pika.BaseConnection):

            def declare_callback_queue(channel: pika.channel.Channel):
                LOGGER.info(f"Creating channel on {self._params._host}")

                self._channel = channel
                while not self._channel.is_open:
                    ...
                self._channel.queue_declare(queue=self._callback_queue)
                for subscription in self._subscriptions:
                    self._subscribe(subscription)
                LOGGER.info(f"Channel created on {self._params._host}")
                self._connection_ready.set()

            while not self._connection.is_open:
                ...
            self._connection.channel(on_open_callback=declare_callback_queue)
            LOGGER.info(f"Connected to {self._params._host}")

        def close_connection(_: pika.BaseConnection, exception):  # TODO: Check for exception
            self._connection = self._thread = self._channel = None
            self._shutdown.set()

        self._connection = pika.SelectConnection(parameters=self._params,
                                                 on_open_callback=declare_channel,
                                                 on_close_callback=close_connection)

        self._thread = Thread(target=self._connection.ioloop.start)
        self._thread.setDaemon(True)
        self._thread.start()
        if not self._connection_ready.wait(timeout=5):
            LOGGER.warning(
                f"Not connected to {self._params._host} after 5 seconds!")  # TODO: loop twice then error then quit?

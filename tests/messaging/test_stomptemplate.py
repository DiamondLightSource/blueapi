import itertools
from collections.abc import Iterable
from concurrent.futures import Future
from queue import Queue
from typing import Any
from unittest.mock import ANY, MagicMock, call, patch

import numpy as np
import pytest
from pydantic import BaseModel, BaseSettings, Field
from stomp import Connection
from stomp.exception import ConnectFailedException, NotConnectedException

from blueapi.config import StompConfig
from blueapi.messaging import MessageContext, MessagingTemplate, StompMessagingTemplate

_TIMEOUT: float = 10.0
_COUNT = itertools.count()


class StompTestingSettings(BaseSettings):
    blueapi_test_stomp_ports: list[int] = Field(default=[61613])

    def test_stomp_configs(self) -> Iterable[StompConfig]:
        for port in self.blueapi_test_stomp_ports:
            yield StompConfig(port=port)


@pytest.fixture(params=StompTestingSettings().test_stomp_configs())
def disconnected_template(request: pytest.FixtureRequest) -> MessagingTemplate:
    stomp_config = request.param
    template = StompMessagingTemplate.autoconfigured(stomp_config)
    assert template is not None
    return template


@pytest.fixture(params=StompTestingSettings().test_stomp_configs())
def template(request: pytest.FixtureRequest) -> Iterable[MessagingTemplate]:
    stomp_config = request.param
    template = StompMessagingTemplate.autoconfigured(stomp_config)
    assert template is not None
    template.connect()
    yield template
    template.disconnect()


@pytest.fixture
def test_queue(template: MessagingTemplate) -> str:
    return template.destinations.queue(f"test-{next(_COUNT)}")


@pytest.fixture
def test_queue_2(template: MessagingTemplate) -> str:
    return template.destinations.queue(f"test-{next(_COUNT)}")


@pytest.fixture
def test_topic(template: MessagingTemplate) -> str:
    return template.destinations.topic(f"test-{next(_COUNT)}")


def test_disconnected_error(template: MessagingTemplate, test_queue: str) -> None:
    acknowledge(template, test_queue)

    f: Future = Future()

    def callback(ctx: MessageContext, message: str) -> None:
        f.set_result(message)

    if template.is_connected():
        template.disconnect()
    with pytest.raises(NotConnectedException):
        template.send(test_queue, "test_message", callback)

    with patch(
        "blueapi.messaging.stomptemplate.LOGGER.info", autospec=True
    ) as mock_logger:
        template.disconnect()
        assert not template.is_connected()
        expected_calls = [
            call("Disconnecting..."),
            call("Already disconnected"),
        ]
        mock_logger.assert_has_calls(expected_calls)


@pytest.mark.stomp
def test_send(template: MessagingTemplate, test_queue: str) -> None:
    f: Future = Future()

    def callback(ctx: MessageContext, message: str) -> None:
        f.set_result(message)

    template.subscribe(test_queue, callback)
    template.send(test_queue, "test_message")
    assert f.result(timeout=_TIMEOUT)


@pytest.mark.stomp
def test_send_to_topic(template: MessagingTemplate, test_topic: str) -> None:
    f: Future = Future()

    def callback(ctx: MessageContext, message: str) -> None:
        f.set_result(message)

    template.subscribe(test_topic, callback)
    template.send(test_topic, "test_message")
    assert f.result(timeout=_TIMEOUT)


@pytest.mark.stomp
def test_send_on_reply(template: MessagingTemplate, test_queue: str) -> None:
    acknowledge(template, test_queue)

    f: Future = Future()

    def callback(ctx: MessageContext, message: str) -> None:
        f.set_result(message)

    template.send(test_queue, "test_message", callback)
    assert f.result(timeout=_TIMEOUT)


@pytest.mark.stomp
def test_send_and_receive(template: MessagingTemplate, test_queue: str) -> None:
    acknowledge(template, test_queue)
    reply = template.send_and_receive(test_queue, "test", str).result(timeout=_TIMEOUT)
    assert reply == "ack"


@pytest.mark.stomp
def test_listener(template: MessagingTemplate, test_queue: str) -> None:
    @template.listener(test_queue)
    def server(ctx: MessageContext, message: str) -> None:
        reply_queue = ctx.reply_destination
        if reply_queue is None:
            raise RuntimeError("reply queue is None")
        template.send(reply_queue, "ack", correlation_id=ctx.correlation_id)

    reply = template.send_and_receive(test_queue, "test", str).result(timeout=_TIMEOUT)
    assert reply == "ack"


class Foo(BaseModel):
    a: int
    b: str


@pytest.mark.stomp
@pytest.mark.parametrize(
    "message,message_type",
    [
        ("test", str),
        (1, int),
        (Foo(a=1, b="test"), Foo),
        (np.array([1, 2, 3]), list),
    ],
)
def test_deserialization(
    template: MessagingTemplate, test_queue: str, message: Any, message_type: type
) -> None:
    def server(ctx: MessageContext, message: message_type) -> None:  # type: ignore
        reply_queue = ctx.reply_destination
        if reply_queue is None:
            raise RuntimeError("reply queue is None")
        template.send(reply_queue, message, correlation_id=ctx.correlation_id)

    template.subscribe(test_queue, server)
    reply = template.send_and_receive(test_queue, message, message_type).result(
        timeout=_TIMEOUT
    )
    if type(message) == np.ndarray:
        message = message.tolist()
    assert reply == message


@pytest.mark.stomp
def test_subscribe_before_connect(
    disconnected_template: MessagingTemplate, test_queue: str
) -> None:
    acknowledge(disconnected_template, test_queue)
    disconnected_template.connect()
    reply = disconnected_template.send_and_receive(test_queue, "test", str).result(
        timeout=_TIMEOUT
    )
    assert reply == "ack"


@pytest.mark.stomp
def test_reconnect(template: MessagingTemplate, test_queue: str) -> None:
    acknowledge(template, test_queue)
    reply = template.send_and_receive(test_queue, "test", str).result(timeout=_TIMEOUT)
    assert reply == "ack"
    template.disconnect()
    assert not template.is_connected()
    template.connect()
    assert template.is_connected()
    reply = template.send_and_receive(test_queue, "test", str).result(timeout=_TIMEOUT)
    assert reply == "ack"


@pytest.fixture()
def failing_template() -> MessagingTemplate:
    def connection_exception(*args, **kwargs):
        raise ConnectFailedException

    connection = Connection()
    connection.connect = MagicMock(side_effect=connection_exception)
    return StompMessagingTemplate(connection)


@pytest.mark.stomp
def test_failed_connect(failing_template: MessagingTemplate, test_queue: str) -> None:
    assert not failing_template.is_connected()
    with patch(
        "blueapi.messaging.stomptemplate.LOGGER.error", autospec=True
    ) as mock_logger:
        failing_template.connect()
        assert not failing_template.is_connected()
        mock_logger.assert_called_once_with(
            "Failed to connect to message bus", exc_info=ANY
        )


@pytest.mark.stomp
def test_correlation_id(
    template: MessagingTemplate, test_queue: str, test_queue_2: str
) -> None:
    correlation_id = "foobar"
    q: Queue = Queue()

    def server(ctx: MessageContext, msg: str) -> None:
        q.put(ctx)
        template.send(test_queue_2, msg, correlation_id=ctx.correlation_id)

    def client(ctx: MessageContext, msg: str) -> None:
        q.put(ctx)

    template.subscribe(test_queue, server)
    template.subscribe(test_queue_2, client)
    template.send(test_queue, "test", None, correlation_id)

    ctx_req: MessageContext = q.get(timeout=_TIMEOUT)
    assert ctx_req.correlation_id == correlation_id
    ctx_ack: MessageContext = q.get(timeout=_TIMEOUT)
    assert ctx_ack.correlation_id == correlation_id


def acknowledge(template: MessagingTemplate, destination: str) -> None:
    def server(ctx: MessageContext, message: str) -> None:
        reply_queue = ctx.reply_destination
        if reply_queue is None:
            raise RuntimeError("reply queue is None")
        template.send(reply_queue, "ack", correlation_id=ctx.correlation_id)

    template.subscribe(destination, server)

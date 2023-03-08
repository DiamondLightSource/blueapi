import itertools
import os
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any, Iterable, Type

import pytest

from blueapi.config import StompConfig
from blueapi.messaging import MessageContext, MessagingTemplate, StompMessagingTemplate

_TIMEOUT: float = 10.0
_COUNT = itertools.count()


@pytest.fixture
def stomp_config() -> StompConfig:
    return StompConfig(host=os.environ.get("STOMP_HOST", "localhost"))


@pytest.fixture
def disconnected_template(stomp_config: StompConfig) -> MessagingTemplate:
    return StompMessagingTemplate.autoconfigured(stomp_config)


@pytest.fixture
def template(disconnected_template: MessagingTemplate) -> Iterable[MessagingTemplate]:
    disconnected_template.connect()
    yield disconnected_template
    disconnected_template.disconnect()


@pytest.fixture
def test_queue(template: MessagingTemplate) -> str:
    return template.destinations.queue(f"test-{next(_COUNT)}")


@pytest.mark.stomp
def test_send(template: MessagingTemplate, test_queue: str) -> None:
    f: Future = Future()

    def callback(ctx: MessageContext, message: str) -> None:
        f.set_result(message)

    template.subscribe(test_queue, callback)
    template.send(test_queue, "test_message")
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
def test_send_and_recieve(template: MessagingTemplate, test_queue: str) -> None:
    acknowledge(template, test_queue)
    reply = template.send_and_recieve(test_queue, "test", str).result(timeout=_TIMEOUT)
    assert reply == "ack"


@dataclass
class Foo:
    a: int
    b: str


@pytest.mark.stomp
@pytest.mark.parametrize(
    "message,message_type",
    [("test", str), (1, int), (Foo(1, "test"), Foo)],
)
def test_deserialization(
    template: MessagingTemplate, test_queue: str, message: Any, message_type: Type
) -> None:
    def server(ctx: MessageContext, message: message_type) -> None:  # type: ignore
        reply_queue = ctx.reply_destination
        if reply_queue is None:
            raise RuntimeError("reply queue is None")
        template.send(reply_queue, message)

    template.subscribe(test_queue, server)
    reply = template.send_and_recieve(test_queue, message, message_type).result(
        timeout=_TIMEOUT
    )
    assert reply == message


@pytest.mark.stomp
def test_subscribe_before_connect(
    disconnected_template: MessagingTemplate, test_queue: str
) -> None:
    acknowledge(disconnected_template, test_queue)
    disconnected_template.connect()
    reply = disconnected_template.send_and_recieve(test_queue, "test", str).result(
        timeout=_TIMEOUT
    )
    assert reply == "ack"


@pytest.mark.stomp
def test_reconnect(template: MessagingTemplate, test_queue: str) -> None:
    acknowledge(template, test_queue)
    reply = template.send_and_recieve(test_queue, "test", str).result(timeout=_TIMEOUT)
    assert reply == "ack"
    template.disconnect()
    template.connect()
    reply = template.send_and_recieve(test_queue, "test", str).result(timeout=_TIMEOUT)
    assert reply == "ack"


def acknowledge(template: MessagingTemplate, test_queue: str) -> None:
    def server(ctx: MessageContext, message: str) -> None:
        reply_queue = ctx.reply_destination
        if reply_queue is None:
            raise RuntimeError("reply queue is None")
        template.send(reply_queue, "ack")

    template.subscribe(test_queue, server)

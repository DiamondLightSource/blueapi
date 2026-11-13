from collections.abc import Iterable
from concurrent.futures import Future
from dataclasses import dataclass
from queue import Queue
from unittest import mock

import pytest

from blueapi.core import EventPublisher

_TIMEOUT: float = 10.0


@dataclass
class MyEvent:
    a: str


@pytest.fixture
def publisher() -> EventPublisher[MyEvent]:
    return EventPublisher()


def test_publishes_event(publisher: EventPublisher[MyEvent]) -> None:
    event = MyEvent("a")
    f: Future = Future()
    publisher.subscribe(lambda r: f.set_result(r))
    publisher.publish(event)
    assert f.result(timeout=_TIMEOUT) == event


def test_multi_subscriber(publisher: EventPublisher[MyEvent]) -> None:
    event = MyEvent("a")
    f1: Future = Future()
    f2: Future = Future()
    publisher.subscribe(lambda r: f1.set_result(r))
    publisher.subscribe(lambda r: f2.set_result(r))
    publisher.publish(event)
    assert f1.result(timeout=_TIMEOUT) == f2.result(timeout=_TIMEOUT) == event


def test_can_unsubscribe(publisher: EventPublisher[MyEvent]) -> None:
    event_a = MyEvent("a")
    event_b = MyEvent("b")
    event_c = MyEvent("c")
    q: Queue = Queue()
    sub = publisher.subscribe(lambda r: q.put(r))
    publisher.publish(event_a)
    publisher.unsubscribe(sub)
    publisher.publish(event_b)
    publisher.subscribe(lambda r: q.put(r))
    publisher.publish(event_c)
    assert list(_drain(q)) == [event_a, event_c]


def test_can_unsubscribe_all(publisher: EventPublisher[MyEvent]) -> None:
    event_a = MyEvent("a")
    event_b = MyEvent("b")
    event_c = MyEvent("c")
    q: Queue = Queue()
    publisher.subscribe(lambda r: q.put(r))
    publisher.subscribe(lambda r: q.put(r))
    publisher.publish(event_a)
    publisher.unsubscribe_all()
    publisher.publish(event_b)
    publisher.subscribe(lambda r: q.put(r))
    publisher.publish(event_c)
    assert list(_drain(q)) == [event_a, event_a, event_c]


def test_callback_exceptions_are_contained(publisher: EventPublisher[MyEvent]):
    event = MyEvent("foo")

    # First call should raise exception, next should be fine
    handler = mock.Mock(side_effect=[ValueError("Bad Event"), ()])
    publisher.subscribe(handler)
    publisher.subscribe(handler)

    with pytest.RaisesGroup(ValueError):
        publisher.publish(event)

    # Both handlers should be called but the exception should still be raised
    handler.assert_has_calls([mock.call(event), mock.call(event)])


def _drain(queue: Queue) -> Iterable:
    while not queue.empty():
        yield queue.get_nowait()

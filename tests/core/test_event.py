from collections.abc import Iterable
from concurrent.futures import Future
from dataclasses import dataclass
from queue import Queue

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
    publisher.subscribe(lambda r, _: f.set_result(r))
    publisher.publish(event)
    assert f.result(timeout=_TIMEOUT) == event


def test_multi_subscriber(publisher: EventPublisher[MyEvent]) -> None:
    event = MyEvent("a")
    f1: Future = Future()
    f2: Future = Future()
    publisher.subscribe(lambda r, _: f1.set_result(r))
    publisher.subscribe(lambda r, _: f2.set_result(r))
    publisher.publish(event)
    assert f1.result(timeout=_TIMEOUT) == f2.result(timeout=_TIMEOUT) == event


def test_can_unsubscribe(publisher: EventPublisher[MyEvent]) -> None:
    event_a = MyEvent("a")
    event_b = MyEvent("b")
    event_c = MyEvent("c")
    q: Queue = Queue()
    sub = publisher.subscribe(lambda r, _: q.put(r))
    publisher.publish(event_a)
    publisher.unsubscribe(sub)
    publisher.publish(event_b)
    publisher.subscribe(lambda r, _: q.put(r))
    publisher.publish(event_c)
    assert list(_drain(q)) == [event_a, event_c]


def test_can_unsubscribe_all(publisher: EventPublisher[MyEvent]) -> None:
    event_a = MyEvent("a")
    event_b = MyEvent("b")
    event_c = MyEvent("c")
    q: Queue = Queue()
    publisher.subscribe(lambda r, _: q.put(r))
    publisher.subscribe(lambda r, _: q.put(r))
    publisher.publish(event_a)
    publisher.unsubscribe_all()
    publisher.publish(event_b)
    publisher.subscribe(lambda r, _: q.put(r))
    publisher.publish(event_c)
    assert list(_drain(q)) == [event_a, event_a, event_c]


def test_correlation_id(publisher: EventPublisher[MyEvent]) -> None:
    event = MyEvent("a")
    correlation_id = "foobar"
    f: Future = Future()
    publisher.subscribe(lambda _, c: f.set_result(c))
    publisher.publish(event, correlation_id)
    assert f.result(timeout=_TIMEOUT) == correlation_id


def _drain(queue: Queue) -> Iterable:
    while not queue.empty():
        yield queue.get_nowait()

from concurrent.futures import Future
from dataclasses import dataclass
from queue import Queue
from typing import Iterable

import pytest

from blueapi.core import EventPublisher


@dataclass
class MyEvent:
    a: str


@pytest.fixture
def publisher() -> EventPublisher[MyEvent]:
    return EventPublisher()


def test_publishes_event(timeout: float, publisher: EventPublisher[MyEvent]) -> None:
    event = MyEvent("a")
    f: Future = Future()
    publisher.subscribe(lambda r, _: f.set_result(r))
    publisher.publish(event)
    assert f.result(timeout=timeout) == event


def test_multi_subscriber(timeout: float, publisher: EventPublisher[MyEvent]) -> None:
    event = MyEvent("a")
    f1: Future = Future()
    f2: Future = Future()
    publisher.subscribe(lambda r, _: f1.set_result(r))
    publisher.subscribe(lambda r, _: f2.set_result(r))
    publisher.publish(event)
    assert f1.result(timeout=timeout) == f2.result(timeout=timeout) == event


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


def test_correlation_id(timeout: float, publisher: EventPublisher[MyEvent]) -> None:
    event = MyEvent("a")
    correlation_id = "foobar"
    f: Future = Future()
    publisher.subscribe(lambda _, c: f.set_result(c))
    publisher.publish(event, correlation_id)
    assert f.result(timeout=timeout) == correlation_id


def _drain(queue: Queue) -> Iterable:
    while not queue.empty():
        yield queue.get_nowait()

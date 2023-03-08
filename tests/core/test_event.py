from concurrent.futures import Future
from dataclasses import dataclass
from queue import Queue
from typing import Iterable

import pytest

from blueapi.core import EventPublisher, EventStream

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
    publisher.subscribe(f.set_result)
    publisher.publish(event)
    assert f.result(timeout=_TIMEOUT) == event


def test_multi_subscriber(publisher: EventPublisher[MyEvent]) -> None:
    event = MyEvent("a")
    f1: Future = Future()
    f2: Future = Future()
    publisher.subscribe(f1.set_result)
    publisher.subscribe(f2.set_result)
    publisher.publish(event)
    assert f1.result(timeout=_TIMEOUT) == f2.result(timeout=_TIMEOUT) == event


def test_can_unsubscribe(publisher: EventPublisher[MyEvent]) -> None:
    event_a = MyEvent("a")
    event_b = MyEvent("b")
    event_c = MyEvent("c")
    q: Queue = Queue()
    sub = publisher.subscribe(q.put)
    publisher.publish(event_a)
    publisher.unsubscribe(sub)
    publisher.publish(event_b)
    publisher.subscribe(q.put)
    publisher.publish(event_c)
    assert list(_drain(q)) == [event_a, event_c]


def test_can_unsubscribe_all(publisher: EventPublisher[MyEvent]) -> None:
    event_a = MyEvent("a")
    event_b = MyEvent("b")
    event_c = MyEvent("c")
    q: Queue = Queue()
    publisher.subscribe(q.put)
    publisher.subscribe(q.put)
    publisher.publish(event_a)
    publisher.unsubscribe_all()
    publisher.publish(event_b)
    publisher.subscribe(q.put)
    publisher.publish(event_c)
    assert list(_drain(q)) == [event_a, event_a, event_c]


def _drain(queue: Queue) -> Iterable:
    while not queue.empty():
        yield queue.get_nowait()

from typing import Any, Callable, List, Mapping

import bluesky.plan_stubs as bps
import bluesky.plans as bp
import pytest
from bluesky import RunEngine
from bluesky.preprocessors import (
    run_decorator,
    run_wrapper,
    set_run_key_decorator,
    set_run_key_wrapper,
    stage_decorator,
    stage_wrapper,
)
from bluesky.protocols import Readable
from ophyd.sim import SynAxis

from blueapi.core import DataEvent, MsgGenerator
from blueapi.plugins.data_writing import data_writing_wrapper


@pytest.fixture
def run_engine() -> RunEngine:
    return RunEngine()


@pytest.fixture(params=[1, 2])
def detectors(request) -> List[Readable]:
    number_of_detectors = request.param
    return [SynAxis(name=f"testI{i}") for i in range(number_of_detectors)]


def simple_run(detectors: List[Readable]) -> MsgGenerator:
    yield from bp.count(detectors)


def multi_run(detectors: List[Readable]) -> MsgGenerator:
    yield from bp.count(detectors)
    yield from bp.count(detectors)


def multi_nested_plan(detectors: List[Readable]) -> MsgGenerator:
    yield from simple_run(detectors)
    yield from simple_run(detectors)


def multi_run_single_stage(detectors: List[Readable]) -> MsgGenerator:
    def stageless_count() -> MsgGenerator:
        return (yield from bps.one_shot(detectors))

    def inner_plan() -> MsgGenerator:
        yield from run_wrapper(stageless_count())
        yield from run_wrapper(stageless_count())

    yield from stage_wrapper(inner_plan(), detectors)


def multi_run_single_stage_multi_group(detectors: List[Readable]) -> MsgGenerator:
    def stageless_count() -> MsgGenerator:
        return (yield from bps.one_shot(detectors))

    def inner_plan() -> MsgGenerator:
        yield from run_wrapper(stageless_count(), md={"scan_number": 1})
        yield from run_wrapper(stageless_count(), md={"scan_number": 1})
        yield from run_wrapper(stageless_count(), md={"scan_number": 2})
        yield from run_wrapper(stageless_count(), md={"scan_number": 2})

    yield from stage_wrapper(inner_plan(), detectors)


@run_decorator(md={"scan_number": 12345})
@set_run_key_decorator("outer")
def nested_run_with_metadata(detectors: List[Readable]) -> MsgGenerator:
    yield from set_run_key_wrapper(bp.count(detectors), "inner")
    yield from set_run_key_wrapper(bp.count(detectors), "inner")


@run_decorator()
@set_run_key_decorator("outer")
def nested_run_without_metadata(detectors: List[Readable]) -> MsgGenerator:
    yield from set_run_key_wrapper(bp.count(detectors), "inner")
    yield from set_run_key_wrapper(bp.count(detectors), "inner")


def test_simple_run_gets_scan_number(
    run_engine: RunEngine, detectors: List[Readable]
) -> None:
    docs = collect_docs(run_engine, simple_run(detectors))
    assert docs[0].name == "start"
    assert docs[0].doc["scan_number"] == 0


@pytest.mark.parametrize("plan", [multi_run, multi_nested_plan])
def test_multi_run_gets_scan_numbers(
    run_engine: RunEngine,
    detectors: List[Readable],
    plan: Callable[[List[Readable]], MsgGenerator],
) -> None:
    docs = collect_docs(run_engine, plan(detectors))
    start_docs = find_start_docs(docs)
    assert len(start_docs) == 2
    assert start_docs[0].doc["scan_number"] == 0
    assert start_docs[1].doc["scan_number"] == 1


def test_multi_run_single_stage(
    run_engine: RunEngine,
    detectors: List[Readable],
) -> None:
    docs = collect_docs(run_engine, multi_run_single_stage(detectors))
    start_docs = find_start_docs(docs)
    assert len(start_docs) == 2
    assert start_docs[0].doc["scan_number"] == 0
    assert start_docs[1].doc["scan_number"] == 0


def test_multi_run_single_stage_multi_group(
    run_engine: RunEngine,
    detectors: List[Readable],
) -> None:
    docs = collect_docs(run_engine, multi_run_single_stage_multi_group(detectors))
    start_docs = find_start_docs(docs)
    assert len(start_docs) == 4
    assert start_docs[0].doc["scan_number"] == 0
    assert start_docs[1].doc["scan_number"] == 0
    assert start_docs[2].doc["scan_number"] == 0
    assert start_docs[3].doc["scan_number"] == 0


def test_nested_run_with_metadata(
    run_engine: RunEngine,
    detectors: List[Readable],
) -> None:
    docs = collect_docs(run_engine, nested_run_with_metadata(detectors))
    start_docs = find_start_docs(docs)
    assert len(start_docs) == 3
    assert start_docs[0].doc["scan_number"] == 0
    assert start_docs[1].doc["scan_number"] == 1
    assert start_docs[2].doc["scan_number"] == 2


def test_nested_run_without_metadata(
    run_engine: RunEngine,
    detectors: List[Readable],
) -> None:
    docs = collect_docs(run_engine, nested_run_without_metadata(detectors))
    start_docs = find_start_docs(docs)
    assert len(start_docs) == 3
    assert start_docs[0].doc["scan_number"] == 0
    assert start_docs[1].doc["scan_number"] == 1
    assert start_docs[2].doc["scan_number"] == 2


def collect_docs(run_engine: RunEngine, plan: MsgGenerator) -> List[DataEvent]:
    events = []

    def on_event(name: str, doc: Mapping[str, Any]) -> None:
        events.append(DataEvent(name=name, doc=doc))

    wrapped_plan = data_writing_wrapper(plan, "exm")
    run_engine(wrapped_plan, on_event)
    return events


def find_start_docs(docs: List[DataEvent]) -> List[DataEvent]:
    return list(filter(lambda event: event.name == "start", docs))

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
    stage_wrapper,
)

from blueapi.core import DataEvent, MsgGenerator
from blueapi.plugins.data_writing import (
    DATA_COLLECTION_NUMBER,
    DataCollectionProvider,
    InMemoryDataCollectionProvider,
    data_writing_wrapper,
)

from .file_writing_detector import FakeFileWritingDetector


@pytest.fixture
def provider() -> DataCollectionProvider:
    return InMemoryDataCollectionProvider("example")


@pytest.fixture
def run_engine() -> RunEngine:
    return RunEngine()


@pytest.fixture(params=[1, 2])
def detectors(
    request, provider: DataCollectionProvider
) -> List[FakeFileWritingDetector]:
    number_of_detectors = request.param
    return [
        FakeFileWritingDetector(
            name=f"test_detector_{i}",
            provider=provider,
        )
        for i in range(number_of_detectors)
    ]


def simple_run(detectors: List[FakeFileWritingDetector]) -> MsgGenerator:
    yield from bp.count(detectors)


def multi_run(detectors: List[FakeFileWritingDetector]) -> MsgGenerator:
    yield from bp.count(detectors)
    yield from bp.count(detectors)


def multi_nested_plan(detectors: List[FakeFileWritingDetector]) -> MsgGenerator:
    yield from simple_run(detectors)
    yield from simple_run(detectors)


def multi_run_single_stage(detectors: List[FakeFileWritingDetector]) -> MsgGenerator:
    def stageless_count() -> MsgGenerator:
        return (yield from bps.one_shot(detectors))

    def inner_plan() -> MsgGenerator:
        yield from run_wrapper(stageless_count())
        yield from run_wrapper(stageless_count())

    yield from stage_wrapper(inner_plan(), detectors)


def multi_run_single_stage_multi_group(
    detectors: List[FakeFileWritingDetector],
) -> MsgGenerator:
    def stageless_count() -> MsgGenerator:
        return (yield from bps.one_shot(detectors))

    def inner_plan() -> MsgGenerator:
        yield from run_wrapper(stageless_count(), md={DATA_COLLECTION_NUMBER: 1})
        yield from run_wrapper(stageless_count(), md={DATA_COLLECTION_NUMBER: 1})
        yield from run_wrapper(stageless_count(), md={DATA_COLLECTION_NUMBER: 2})
        yield from run_wrapper(stageless_count(), md={DATA_COLLECTION_NUMBER: 2})

    yield from stage_wrapper(inner_plan(), detectors)


@run_decorator(md={DATA_COLLECTION_NUMBER: 12345})
@set_run_key_decorator("outer")
def nested_run_with_metadata(detectors: List[FakeFileWritingDetector]) -> MsgGenerator:
    yield from set_run_key_wrapper(bp.count(detectors), "inner")
    yield from set_run_key_wrapper(bp.count(detectors), "inner")


@run_decorator()
@set_run_key_decorator("outer")
def nested_run_without_metadata(
    detectors: List[FakeFileWritingDetector],
) -> MsgGenerator:
    yield from set_run_key_wrapper(bp.count(detectors), "inner")
    yield from set_run_key_wrapper(bp.count(detectors), "inner")


def test_simple_run_gets_scan_number(
    run_engine: RunEngine,
    detectors: List[FakeFileWritingDetector],
    provider: DataCollectionProvider,
) -> None:
    docs = collect_docs(
        run_engine,
        simple_run(detectors),
        provider,
    )
    assert docs[0].name == "start"
    assert docs[0].doc[DATA_COLLECTION_NUMBER] == 0
    assert_all_detectors_used_collection_numbers(docs, detectors, [0])


@pytest.mark.parametrize("plan", [multi_run, multi_nested_plan])
def test_multi_run_gets_scan_numbers(
    run_engine: RunEngine,
    detectors: List[FakeFileWritingDetector],
    plan: Callable[[List[FakeFileWritingDetector]], MsgGenerator],
    provider: DataCollectionProvider,
) -> None:
    docs = collect_docs(
        run_engine,
        plan(detectors),
        provider,
    )
    start_docs = find_start_docs(docs)
    assert len(start_docs) == 2
    assert start_docs[0].doc[DATA_COLLECTION_NUMBER] == 0
    assert start_docs[1].doc[DATA_COLLECTION_NUMBER] == 1
    assert_all_detectors_used_collection_numbers(docs, detectors, [0, 1])


def test_multi_run_single_stage(
    run_engine: RunEngine,
    detectors: List[FakeFileWritingDetector],
    provider: DataCollectionProvider,
) -> None:
    docs = collect_docs(
        run_engine,
        multi_run_single_stage(detectors),
        provider,
    )
    start_docs = find_start_docs(docs)
    assert len(start_docs) == 2
    assert start_docs[0].doc[DATA_COLLECTION_NUMBER] == 0
    assert start_docs[1].doc[DATA_COLLECTION_NUMBER] == 0
    assert_all_detectors_used_collection_numbers(docs, detectors, [0, 0])


def test_multi_run_single_stage_multi_group(
    run_engine: RunEngine,
    detectors: List[FakeFileWritingDetector],
    provider: DataCollectionProvider,
) -> None:
    docs = collect_docs(
        run_engine,
        multi_run_single_stage_multi_group(detectors),
        provider,
    )
    start_docs = find_start_docs(docs)
    assert len(start_docs) == 4
    assert start_docs[0].doc[DATA_COLLECTION_NUMBER] == 0
    assert start_docs[1].doc[DATA_COLLECTION_NUMBER] == 0
    assert start_docs[2].doc[DATA_COLLECTION_NUMBER] == 0
    assert start_docs[3].doc[DATA_COLLECTION_NUMBER] == 0
    assert_all_detectors_used_collection_numbers(docs, detectors, [0, 0, 0, 0])


def test_nested_run_with_metadata(
    run_engine: RunEngine,
    detectors: List[FakeFileWritingDetector],
    provider: DataCollectionProvider,
) -> None:
    docs = collect_docs(
        run_engine,
        nested_run_with_metadata(detectors),
        provider,
    )
    start_docs = find_start_docs(docs)
    assert len(start_docs) == 3
    assert start_docs[0].doc[DATA_COLLECTION_NUMBER] == 0
    assert start_docs[1].doc[DATA_COLLECTION_NUMBER] == 1
    assert start_docs[2].doc[DATA_COLLECTION_NUMBER] == 2
    assert_all_detectors_used_collection_numbers(docs, detectors, [1, 2])


def test_nested_run_without_metadata(
    run_engine: RunEngine,
    detectors: List[FakeFileWritingDetector],
    provider: DataCollectionProvider,
) -> None:
    docs = collect_docs(
        run_engine,
        nested_run_without_metadata(detectors),
        provider,
    )
    start_docs = find_start_docs(docs)
    assert len(start_docs) == 3
    assert start_docs[0].doc[DATA_COLLECTION_NUMBER] == 0
    assert start_docs[1].doc[DATA_COLLECTION_NUMBER] == 1
    assert start_docs[2].doc[DATA_COLLECTION_NUMBER] == 2
    assert_all_detectors_used_collection_numbers(docs, detectors, [1, 2])


def collect_docs(
    run_engine: RunEngine,
    plan: MsgGenerator,
    provider: DataCollectionProvider,
) -> List[DataEvent]:
    events = []

    def on_event(name: str, doc: Mapping[str, Any]) -> None:
        events.append(DataEvent(name=name, doc=doc))

    wrapped_plan = data_writing_wrapper(plan, provider)
    run_engine(wrapped_plan, on_event)
    return events


def assert_all_detectors_used_collection_numbers(
    docs: List[DataEvent],
    detectors: List[FakeFileWritingDetector],
    collection_number_history: List[int],
) -> None:
    descriptors = find_descriptor_docs(docs)
    assert len(descriptors) == len(collection_number_history)

    for descriptor, collection_number in zip(descriptors, collection_number_history):
        for detector in detectors:
            attr_name = f"{detector.name}_collection_number"
            actual_collection_number = (
                descriptor.doc.get("configuration", {})
                .get(detector.name, {})
                .get("data", {})[attr_name]
            )
            assert actual_collection_number == collection_number


def find_start_docs(docs: List[DataEvent]) -> List[DataEvent]:
    return list(filter(lambda event: event.name == "start", docs))


def find_descriptor_docs(docs: List[DataEvent]) -> List[DataEvent]:
    return list(filter(lambda event: event.name == "descriptor", docs))

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

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
from bluesky.protocols import HasName, Readable, Reading, Status, Triggerable
from event_model.documents.event_descriptor import DataKey
from ophyd.status import StatusBase
from ophyd_async.core import DirectoryProvider

from blueapi.core import DataEvent, MsgGenerator
from blueapi.data_management.visit_directory_provider import (
    DataCollectionIdentifier,
    VisitDirectoryProvider,
    VisitServiceClient,
)
from blueapi.preprocessors.attach_metadata import DATA_SESSION, attach_metadata

DATA_DIRECTORY = Path("/tmp")
DATA_GROUP_NAME = "test"


RUN_0 = DATA_DIRECTORY / f"{DATA_GROUP_NAME}-0"
RUN_1 = DATA_DIRECTORY / f"{DATA_GROUP_NAME}-1"
RUN_2 = DATA_DIRECTORY / f"{DATA_GROUP_NAME}-2"


class MockVisitServiceClient(VisitServiceClient):
    _count: int
    _fail: bool

    def __init__(self) -> None:
        super().__init__("http://example.com")
        self._count = 0
        self._fail = False

    def always_fail(self) -> None:
        self._fail = True

    async def create_new_collection(self) -> DataCollectionIdentifier:
        if self._fail:
            raise ConnectionError()

        count = self._count
        self._count += 1
        return DataCollectionIdentifier(collectionNumber=count)

    async def get_current_collection(self) -> DataCollectionIdentifier:
        if self._fail:
            raise ConnectionError()

        return DataCollectionIdentifier(collectionNumber=self._count)


@pytest.fixture
def client() -> VisitServiceClient:
    return MockVisitServiceClient()


@pytest.fixture
def provider(client: VisitServiceClient) -> VisitDirectoryProvider:
    return VisitDirectoryProvider(
        data_directory=DATA_DIRECTORY,
        data_group_name=DATA_GROUP_NAME,
        client=client,
    )


@pytest.fixture
def run_engine() -> RunEngine:
    return RunEngine()


class FakeDetector(Readable, HasName, Triggerable):
    _name: str
    _provider: DirectoryProvider

    def __init__(
        self,
        name: str,
        provider: DirectoryProvider,
    ) -> None:
        self._name = name
        self._provider = provider

    async def read(self) -> dict[str, Reading]:
        return {
            f"{self.name}_data": {
                "value": "test",
                "timestamp": 0.0,
            },
        }

    async def describe(self) -> dict[str, DataKey]:
        directory_info = self._provider()
        path = f"{directory_info.directory_path}/{directory_info.filename_prefix}"
        return {
            f"{self.name}_data": {
                "dtype": "string",
                "shape": [1],
                "source": path,
            }
        }

    def trigger(self) -> Status:
        status = StatusBase()
        status.set_finished()
        return status

    @property
    def name(self) -> str:
        return self._name

    @property
    def parent(self) -> None:
        return None


@pytest.fixture(params=[1, 2])
def detectors(request, provider: VisitDirectoryProvider) -> list[Readable]:
    number_of_detectors = request.param
    return [
        FakeDetector(
            name=f"test_detector_{i}",
            provider=provider,
        )
        for i in range(number_of_detectors)
    ]


def simple_run(detectors: list[Readable]) -> MsgGenerator:
    yield from bp.count(detectors)


def multi_run(detectors: list[Readable]) -> MsgGenerator:
    yield from bp.count(detectors)
    yield from bp.count(detectors)


def multi_nested_plan(detectors: list[Readable]) -> MsgGenerator:
    yield from simple_run(detectors)
    yield from simple_run(detectors)


def multi_run_single_stage(detectors: list[Readable]) -> MsgGenerator:
    def stageless_count() -> MsgGenerator:
        return (yield from bps.one_shot(detectors))

    def inner_plan() -> MsgGenerator:
        yield from run_wrapper(stageless_count())
        yield from run_wrapper(stageless_count())

    yield from stage_wrapper(inner_plan(), detectors)


def multi_run_single_stage_multi_group(
    detectors: list[Readable],
) -> MsgGenerator:
    def stageless_count() -> MsgGenerator:
        return (yield from bps.one_shot(detectors))

    def inner_plan() -> MsgGenerator:
        yield from run_wrapper(stageless_count(), md={DATA_SESSION: 1})
        yield from run_wrapper(stageless_count(), md={DATA_SESSION: 1})
        yield from run_wrapper(stageless_count(), md={DATA_SESSION: 2})
        yield from run_wrapper(stageless_count(), md={DATA_SESSION: 2})

    yield from stage_wrapper(inner_plan(), detectors)


@run_decorator(md={DATA_SESSION: 12345})
@set_run_key_decorator("outer")
def nested_run_with_metadata(detectors: list[Readable]) -> MsgGenerator:
    yield from set_run_key_wrapper(bp.count(detectors), "inner")
    yield from set_run_key_wrapper(bp.count(detectors), "inner")


@run_decorator()
@set_run_key_decorator("outer")
def nested_run_without_metadata(
    detectors: list[Readable],
) -> MsgGenerator:
    yield from set_run_key_wrapper(bp.count(detectors), "inner")
    yield from set_run_key_wrapper(bp.count(detectors), "inner")


def test_simple_run_gets_scan_number(
    run_engine: RunEngine,
    detectors: list[Readable],
    provider: DirectoryProvider,
) -> None:
    docs = collect_docs(
        run_engine,
        simple_run(detectors),
        provider,
    )
    assert docs[0].name == "start"
    assert docs[0].doc[DATA_SESSION] == f"{DATA_GROUP_NAME}-0"
    assert_all_detectors_used_collection_numbers(docs, detectors, [RUN_0])


@pytest.mark.parametrize("plan", [multi_run, multi_nested_plan])
def test_multi_run_gets_scan_numbers(
    run_engine: RunEngine,
    detectors: list[Readable],
    plan: Callable[[list[Readable]], MsgGenerator],
    provider: DirectoryProvider,
) -> None:
    """Test is here to demonstrate that multi run plans will overwrite files."""
    docs = collect_docs(
        run_engine,
        plan(detectors),
        provider,
    )
    start_docs = find_start_docs(docs)
    assert len(start_docs) == 2
    assert start_docs[0].doc[DATA_SESSION] == f"{DATA_GROUP_NAME}-0"
    assert start_docs[1].doc[DATA_SESSION] == f"{DATA_GROUP_NAME}-0"
    assert_all_detectors_used_collection_numbers(docs, detectors, [RUN_0, RUN_0])


def test_multi_run_single_stage(
    run_engine: RunEngine,
    detectors: list[Readable],
    provider: DirectoryProvider,
) -> None:
    docs = collect_docs(
        run_engine,
        multi_run_single_stage(detectors),
        provider,
    )
    start_docs = find_start_docs(docs)
    assert len(start_docs) == 2
    assert start_docs[0].doc[DATA_SESSION] == f"{DATA_GROUP_NAME}-0"
    assert start_docs[1].doc[DATA_SESSION] == f"{DATA_GROUP_NAME}-0"
    assert_all_detectors_used_collection_numbers(
        docs,
        detectors,
        [
            RUN_0,
            RUN_0,
        ],
    )


def test_multi_run_single_stage_multi_group(
    run_engine: RunEngine,
    detectors: list[Readable],
    provider: DirectoryProvider,
) -> None:
    docs = collect_docs(
        run_engine,
        multi_run_single_stage_multi_group(detectors),
        provider,
    )
    start_docs = find_start_docs(docs)
    assert len(start_docs) == 4
    assert start_docs[0].doc[DATA_SESSION] == f"{DATA_GROUP_NAME}-0"
    assert start_docs[1].doc[DATA_SESSION] == f"{DATA_GROUP_NAME}-0"
    assert start_docs[2].doc[DATA_SESSION] == f"{DATA_GROUP_NAME}-0"
    assert start_docs[3].doc[DATA_SESSION] == f"{DATA_GROUP_NAME}-0"
    assert_all_detectors_used_collection_numbers(
        docs,
        detectors,
        [
            RUN_0,
            RUN_0,
            RUN_0,
            RUN_0,
        ],
    )


def test_nested_run_with_metadata(
    run_engine: RunEngine,
    detectors: list[Readable],
    provider: DirectoryProvider,
) -> None:
    """Test is here to demonstrate that nested runs will be treated as a single run.

    That means detectors in such runs will overwrite files.
    """
    docs = collect_docs(
        run_engine,
        nested_run_with_metadata(detectors),
        provider,
    )
    start_docs = find_start_docs(docs)
    assert len(start_docs) == 3
    assert start_docs[0].doc[DATA_SESSION] == f"{DATA_GROUP_NAME}-0"
    assert start_docs[1].doc[DATA_SESSION] == f"{DATA_GROUP_NAME}-0"
    assert start_docs[2].doc[DATA_SESSION] == f"{DATA_GROUP_NAME}-0"
    assert_all_detectors_used_collection_numbers(docs, detectors, [RUN_0, RUN_0])


def test_nested_run_without_metadata(
    run_engine: RunEngine,
    detectors: list[Readable],
    provider: DirectoryProvider,
) -> None:
    """Test is here to demonstrate that nested runs will be treated as a single run.

    That means detectors in such runs will overwrite files.
    """
    docs = collect_docs(
        run_engine,
        nested_run_without_metadata(detectors),
        provider,
    )
    start_docs = find_start_docs(docs)
    assert len(start_docs) == 3
    assert start_docs[0].doc[DATA_SESSION] == f"{DATA_GROUP_NAME}-0"
    assert start_docs[1].doc[DATA_SESSION] == f"{DATA_GROUP_NAME}-0"
    assert start_docs[2].doc[DATA_SESSION] == f"{DATA_GROUP_NAME}-0"
    assert_all_detectors_used_collection_numbers(docs, detectors, [RUN_0, RUN_0])


def test_visit_directory_provider_fails(
    run_engine: RunEngine,
    detectors: list[Readable],
    provider: DirectoryProvider,
    client: MockVisitServiceClient,
) -> None:
    client.always_fail()
    with pytest.raises(ValueError):
        collect_docs(
            run_engine,
            simple_run(detectors),
            provider,
        )


def test_visit_directory_provider_fails_after_one_sucess(
    run_engine: RunEngine,
    detectors: list[Readable],
    provider: DirectoryProvider,
    client: MockVisitServiceClient,
) -> None:
    collect_docs(
        run_engine,
        simple_run(detectors),
        provider,
    )
    client.always_fail()
    with pytest.raises(ValueError):
        collect_docs(
            run_engine,
            simple_run(detectors),
            provider,
        )


def collect_docs(
    run_engine: RunEngine,
    plan: MsgGenerator,
    provider: DirectoryProvider,
) -> list[DataEvent]:
    events = []

    def on_event(name: str, doc: Mapping[str, Any]) -> None:
        events.append(DataEvent(name=name, doc=doc))

    wrapped_plan = attach_metadata(plan, provider)
    run_engine(wrapped_plan, on_event)
    return events


def assert_all_detectors_used_collection_numbers(
    docs: list[DataEvent],
    detectors: list[Readable],
    source_history: list[Path],
) -> None:
    descriptors = find_descriptor_docs(docs)
    assert len(descriptors) == len(source_history)

    for descriptor, expected_source in zip(descriptors, source_history, strict=False):
        for detector in detectors:
            source = descriptor.doc.get("data_keys", {}).get(f"{detector.name}_data")[
                "source"
            ]
            assert Path(source) == expected_source


def find_start_docs(docs: list[DataEvent]) -> list[DataEvent]:
    return list(filter(lambda event: event.name == "start", docs))


def find_descriptor_docs(docs: list[DataEvent]) -> list[DataEvent]:
    return list(filter(lambda event: event.name == "descriptor", docs))

from pathlib import Path
from typing import Any, Dict, List, Mapping

import bluesky.plans as bp
import pytest
from bluesky import RunEngine
from bluesky.protocols import HasName, Readable, Reading, Status, Triggerable
from event_model.documents.event_descriptor import DataKey
from ophyd.status import StatusBase
from ophyd_async.core import DirectoryProvider, StaticDirectoryProvider

from blueapi.core import DataEvent, MsgGenerator
from blueapi.preprocessors.attach_metadata import DATA_SESSION, attach_metadata

DATA_DIRECTORY = Path("/tmp")
DATA_GROUP_NAME = "test"


RUN_0 = DATA_DIRECTORY / f"{DATA_GROUP_NAME}"
RUN_1 = DATA_DIRECTORY / f"{DATA_GROUP_NAME}"
RUN_2 = DATA_DIRECTORY / f"{DATA_GROUP_NAME}"


@pytest.fixture
def provider() -> DirectoryProvider:
    return StaticDirectoryProvider(str(DATA_DIRECTORY), DATA_GROUP_NAME)


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

    async def read(self) -> Dict[str, Reading]:
        return {
            f"{self.name}_data": {
                "value": "test",
                "timestamp": 0.0,
            },
        }

    async def describe(self) -> Dict[str, DataKey]:
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
def detectors(request, provider: DirectoryProvider) -> List[Readable]:
    number_of_detectors = request.param
    return [
        FakeDetector(
            name=f"test_detector_{i}",
            provider=provider,
        )
        for i in range(number_of_detectors)
    ]


def collect_docs(
    run_engine: RunEngine,
    plan: MsgGenerator,
    provider: DirectoryProvider,
) -> List[DataEvent]:
    events = []

    def on_event(name: str, doc: Mapping[str, Any]) -> None:
        events.append(DataEvent(name=name, doc=doc))

    wrapped_plan = attach_metadata(plan, provider)
    run_engine(wrapped_plan, on_event)
    return events


def test_attach_metadata_attaches_correct_data_session(
    detectors: List[Readable], provider: DirectoryProvider, run_engine: RunEngine
):
    docs = collect_docs(
        run_engine,
        attach_metadata(bp.count(detectors), provider),
        provider,
    )
    assert docs[0].name == "start"
    assert docs[0].doc.get(DATA_SESSION) == DATA_GROUP_NAME

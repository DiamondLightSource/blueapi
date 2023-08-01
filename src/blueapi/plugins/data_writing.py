import itertools
from abc import ABC, abstractmethod, abstractproperty
from pathlib import Path
from typing import Optional

import bluesky.plan_stubs as bps
from aiohttp import ClientSession
from bluesky.utils import make_decorator

from blueapi.core import MsgGenerator
from blueapi.plugins.data_writing_server import DataCollection

from .data_writing_server import DataCollection, DataCollectionSetupResult

DATA_COLLECTION_NUMBER = "data_collection_number"


class DataCollectionProvider(ABC):
    @abstractproperty
    def current_data_collection(self) -> Optional[DataCollection]:
        ...

    @abstractmethod
    async def update(self) -> None:
        ...


class ServiceDataCollectionProvider(DataCollectionProvider):
    _collection_group: str
    _current_collection: Optional[DataCollection]

    def __init__(self, collection_group: str) -> None:
        self._collection_group = collection_group
        self._current_collection = None

    @property
    def current_data_collection(self) -> Optional[DataCollection]:
        return self._current_collection

    async def update(self) -> None:
        async with ClientSession() as session:
            async with session.post(
                f"http://localhost:8089/collection/{self._collection_group}"
            ) as response:
                if response.status == 200:
                    json = await response.json()
                    result = DataCollectionSetupResult.parse_obj(json)
                else:
                    raise Exception(response.status)
        if result.directories_created:
            result.collection
        else:
            raise Exception()


class InMemoryDataCollectionProvider(DataCollectionProvider):
    _collection_group: str
    _scan_number: itertools.count
    _current_collection: Optional[DataCollection]

    def __init__(self, collection_group: str) -> None:
        self._collection_group = collection_group
        self._scan_number = itertools.count()
        self._current_collection = None

    @property
    def current_data_collection(self) -> Optional[DataCollection]:
        return self._current_collection

    async def update(self) -> None:
        scan_number = next(self._scan_number)
        self._current_collection = DataCollection(
            collection_number=scan_number,
            group=self._collection_group,
            raw_data_files_root=Path(f"/tmp/{self._collection_group}"),
            nexus_file_path=Path(f"/tmp{self._collection_group}.nxs"),
        )


def data_writing_wrapper(
    plan: MsgGenerator,
    provider: DataCollectionProvider,
) -> MsgGenerator:
    staging = False
    for message in plan:
        if message.command == "stage":
            if not staging:
                yield from bps.wait_for([provider.update])
                staging = True
            if provider.current_data_collection is None:
                raise Exception("There is no active data collection")
        elif staging:
            staging = False

        if message.command == "open_run":
            if provider.current_data_collection is None:
                yield from bps.wait_for([provider.update])
            if provider.current_data_collection is None:
                raise Exception("There is no active data collection")
            message.kwargs[
                DATA_COLLECTION_NUMBER
            ] = provider.current_data_collection.collection_number
        yield message


data_writing_decorator = make_decorator(data_writing_wrapper)

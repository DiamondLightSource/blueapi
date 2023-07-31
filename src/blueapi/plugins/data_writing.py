import itertools
from abc import ABC, abstractmethod
from collections import deque
from pathlib import Path
from typing import (
    Any,
    Callable,
    Deque,
    Dict,
    Generic,
    Iterable,
    List,
    Optional,
    Protocol,
    TypeVar,
    runtime_checkable,
)

import bluesky.plan_stubs as bps
import requests
from bluesky.protocols import Movable
from bluesky.utils import Msg, make_decorator
from ophyd.areadetector.filestore_mixins import FileStoreBase

from blueapi.core import BlueskyContext, Device, MsgGenerator, walk_devices
from blueapi.plugins.data_writing_server import DataCollection

from .data_writing_server import DataCollection, DataCollectionSetupResult


class DataCollectionProvider(ABC):
    @abstractmethod
    def get_next_data_collection(self, collection_group: str) -> DataCollection:
        ...


class ServiceDataCollectionProvider(DataCollectionProvider):
    def get_next_data_collection(self, collection_group: str) -> DataCollection:
        reply = requests.post(f"http://localhost:8089/collection/{collection_group}")
        result = DataCollectionSetupResult.parse_obj(reply.json())
        if result.directories_created:
            return result.collection
        else:
            raise Exception()


class InMemoryDataCollectionProvider(DataCollectionProvider):
    _scan_number: itertools.count

    def __init__(self) -> None:
        self._scan_number = itertools.count()

    def get_next_data_collection(self, collection_group: str) -> DataCollection:
        scan_number = next(self._scan_number)
        return DataCollection(
            collection_number=scan_number,
            group=collection_group,
            raw_data_files_root=Path(f"/tmp/{collection_group}"),
            nexus_file_path=Path(f"/tmp{collection_group}.nxs"),
        )


def data_writing_wrapper(
    plan: MsgGenerator,
    collection_group: str,
    provider: Optional[DataCollectionProvider] = None,
) -> MsgGenerator:
    if provider is None:
        provider = InMemoryDataCollectionProvider()

    scan_number = itertools.count()
    next_scan_number = None
    stage_stack: Deque = deque()
    # scan_number_stack: Deque = deque()
    for message in plan:
        if message.command == "stage":
            stage_stack.append(message.obj)
        elif stage_stack:
            next_scan_number = next(scan_number)
            root_devices = []
            while stage_stack:
                root_devices.append(stage_stack.pop())
            all_devices = walk_devices(root_devices)
            collection = provider.get_next_data_collection(collection_group)
            configure_data_writing(all_devices, collection)

        if message.command == "open_run":
            if next_scan_number is None:
                next_scan_number = next(scan_number)
            message.kwargs["scan_number"] = next_scan_number
        yield message


data_writing_decorator = make_decorator(data_writing_wrapper)


def configure_data_writing(
    devices: Iterable[Device],
    collection: DataCollection,
) -> None:
    for device in devices:
        if isinstance(device, FileStoreBase):
            path_template = str(collection.raw_data_files_root)

            # Configure Ophyd Device to setup HDF5 writer
            device.reg_root = "/"
            device.read_path_template = path_template
            device.write_path_template = path_template

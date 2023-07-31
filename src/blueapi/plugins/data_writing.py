import itertools
from abc import ABC, abstractmethod
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
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

from .data_writing_server import DataCollection, DataCollectionSetupResult


def data_writing_wrapper(plan: MsgGenerator, collection_group: str) -> MsgGenerator:
    scan_number = itertools.count()
    for message in plan:
        if message.command == "stage":
            next_scan_number = next(scan_number)
            root_devices = relevant_devices(message)
            all_devices = walk_devices(root_devices)
            collection = get_data_collection(collection_group)
            configure_data_writing(all_devices, collection)
        elif message.command == "open_run" and "scan_number" not in message.kwargs:
            message.kwargs["scan_number"] = next_scan_number
        yield message


def relevant_devices(message: Msg) -> Iterable[Device]:
    if isinstance(message.obj, list):
        obj = message.obj
    else:
        obj = [message.obj]
    return obj


data_writing_decorator = make_decorator(data_writing_wrapper)


def get_data_collection(collection_group: str) -> DataCollection:
    reply = requests.post(f"http://localhost:8089/collection/{collection_group}")
    result = DataCollectionSetupResult.parse_obj(reply.json())
    if result.directories_created:
        return result.collection
    else:
        raise Exception()


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

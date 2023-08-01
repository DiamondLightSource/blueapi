import itertools
import os
from pathlib import Path
from typing import Dict

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

SCAN_NUMBER = itertools.count()


class DataCollection(BaseModel):
    collection_number: int
    group: str
    raw_data_files_root: Path
    nexus_file_path: Path


class DataCollectionSetupResult(BaseModel):
    collection: DataCollection
    directories_created: bool


COLLECTIONS: Dict[str, Dict[int, DataCollection]] = {}


@app.post("/collection/{group}")
def create_collection(group: str) -> DataCollectionSetupResult:
    num = next(SCAN_NUMBER)
    if group not in COLLECTIONS:
        COLLECTIONS[group] = {}
    if num in COLLECTIONS[group]:
        raise Exception("Collection already exists")

    data_root = get_data_root(group)
    raw_data_files_root = data_root / f"{group}-{num}"
    nexus_file_path = data_root / f"{group}-{num}.nxs"

    collection = DataCollection(
        collection_number=num,
        group=group,
        raw_data_files_root=raw_data_files_root,
        nexus_file_path=nexus_file_path,
    )

    ensure_directories(collection)
    COLLECTIONS[group][num] = collection

    return DataCollectionSetupResult(
        collection=collection,
        directories_created=True,
    )


def ensure_directories(collection: DataCollection) -> None:
    root = collection.raw_data_files_root
    os.makedirs(root, exist_ok=True)
    if not (root.exists() or root.is_dir()):
        raise Exception("Unable to make data directory")


def get_data_root(group: str) -> Path:
    return Path(f"/tmp/data/{group}")


@app.get("/collection/{group}/{number}")
def get_collection(group: str, number: int) -> DataCollection:
    return COLLECTIONS[group][number]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, port=8089)

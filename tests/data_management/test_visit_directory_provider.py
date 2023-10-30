from pathlib import Path

import pytest
from ophyd_async.core import DirectoryInfo

from blueapi.data_management.visit_directory_provider import (
    DataCollectionIdentifier,
    LocalVisitServiceClient,
    VisitDirectoryProvider,
    VisitServiceClientBase,
)


@pytest.fixture
def visit_service_client() -> VisitServiceClientBase:
    return LocalVisitServiceClient()


@pytest.fixture
def visit_directory_provider(
    visit_service_client: VisitServiceClientBase,
) -> VisitDirectoryProvider:
    return VisitDirectoryProvider("example", Path("/tmp"), visit_service_client)


@pytest.mark.asyncio
async def test_client_can_view_collection(
    visit_service_client: VisitServiceClientBase,
) -> None:
    collection = await visit_service_client.get_current_collection()
    assert collection == DataCollectionIdentifier(collectionNumber=0)


@pytest.mark.asyncio
async def test_client_can_create_collection(
    visit_service_client: VisitServiceClientBase,
) -> None:
    collection = await visit_service_client.create_new_collection()
    assert collection == DataCollectionIdentifier(collectionNumber=1)


@pytest.mark.asyncio
async def test_update_sets_collection_number(
    visit_directory_provider: VisitDirectoryProvider,
) -> None:
    await visit_directory_provider.update()
    assert visit_directory_provider() == DirectoryInfo(
        directory_path="/tmp",
        filename_prefix="example-1",
    )


@pytest.mark.asyncio
async def test_update_sets_collection_number_multi(
    visit_directory_provider: VisitDirectoryProvider,
) -> None:
    await visit_directory_provider.update()
    assert visit_directory_provider() == DirectoryInfo(
        directory_path="/tmp",
        filename_prefix="example-1",
    )
    await visit_directory_provider.update()
    assert visit_directory_provider() == DirectoryInfo(
        directory_path="/tmp",
        filename_prefix="example-2",
    )

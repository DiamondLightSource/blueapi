from pathlib import Path

import pytest
import responses

from blueapi.client.numtracker import (
    DirectoryPath,
    NumtrackerClient,
    NumtrackerScanMutationResponse,
    ScanPaths,
)


@pytest.fixture
def numtracker() -> NumtrackerClient:
    return NumtrackerClient("https://numtracker-example.com/graphql", {})


def test_create_scan(
    numtracker: NumtrackerClient,
    mock_numtracker_server: responses.RequestsMock,
):
    scan = numtracker.create_scan("cm12345-1", "i22")
    assert scan == NumtrackerScanMutationResponse(
        scan=ScanPaths(
            scanFile="p46-11",
            scanNumber=11,
            directory=DirectoryPath(
                instrument="p46",
                instrumentSession="p46-1",
                path=Path("/exports/mybeamline/data/2025"),
            ),
        )
    )

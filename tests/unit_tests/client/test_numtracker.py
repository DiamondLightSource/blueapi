from pathlib import Path

import pytest
import responses
from requests import HTTPError

from blueapi.client.numtracker import (
    DirectoryPath,
    NumtrackerClient,
    NumtrackerScanMutationResponse,
    ScanPaths,
)


@pytest.fixture
def numtracker() -> NumtrackerClient:
    return NumtrackerClient("https://numtracker-example.com/graphql")


def test_create_scan(
    numtracker: NumtrackerClient,
    mock_numtracker_server: responses.RequestsMock,
):
    scan = numtracker.create_scan("ab123", "p46")
    assert scan == NumtrackerScanMutationResponse(
        scan=ScanPaths(
            scanFile="p46-11",
            scanNumber=11,
            directory=DirectoryPath(
                instrument="p46",
                instrumentSession="ab123",
                path=Path("/exports/mybeamline/data/2025"),
            ),
        )
    )


def test_create_scan_raises_400_error(
    numtracker: NumtrackerClient,
    mock_numtracker_server: responses.RequestsMock,
):
    with pytest.raises(
        HTTPError,
        match="400 Client Error: Bad Request for url: https://numtracker-example.com/graphql",
    ):
        numtracker.create_scan("ab123", "p47")


def test_create_scan_raises_500_error(
    numtracker: NumtrackerClient,
    mock_numtracker_server: responses.RequestsMock,
):
    with pytest.raises(
        HTTPError,
        match="500 Server Error: Internal Server Error for url: https://numtracker-example.com/graphql",
    ):
        numtracker.create_scan("ab123", "p48")


def test_create_scan_raises_key_error_on_incorrectly_formatted_responses(
    numtracker: NumtrackerClient,
    mock_numtracker_server: responses.RequestsMock,
):
    with pytest.raises(
        KeyError,
        match="data",
    ):
        numtracker.create_scan("ab123", "p49")

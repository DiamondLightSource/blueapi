from pathlib import Path

import httpx
import pytest
from pydantic import HttpUrl
from pytest_httpx import HTTPXMock

from blueapi.utils.numtracker import (
    DirectoryPath,
    NumtrackerClient,
    NumtrackerScanMutationResponse,
    ScanPaths,
)


@pytest.fixture
def numtracker() -> NumtrackerClient:
    return NumtrackerClient(HttpUrl("https://numtracker-example.com/graphql"))


URL = "https://numtracker-example.com/graphql"

EMPTY = {}

ERRORS = {
    "data": None,
    "errors": [
        {
            "message": "No configuration available for instrument p46",
            "locations": [{"line": 3, "column": 5}],
            "path": ["scan"],
        }
    ],
}


async def test_create_scan(
    numtracker: NumtrackerClient, httpx_mock: HTTPXMock, nt_query, nt_response
):
    httpx_mock.add_response(
        method="POST",
        url=URL,
        match_json=nt_query,
        status_code=200,
        json=nt_response,
    )
    scan = await numtracker.create_scan("ab123", "p46")
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


async def test_create_scan_raises_400_error(
    numtracker: NumtrackerClient, httpx_mock: HTTPXMock, nt_query
):
    httpx_mock.add_response(
        method="POST", url=URL, match_json=nt_query, status_code=400, json=EMPTY
    )
    with pytest.raises(
        httpx.HTTPStatusError,
        match="Client error '400 Bad Request' for url 'https://numtracker-example.com/graphql'",
    ):
        await numtracker.create_scan("ab123", "p46")


async def test_create_scan_raises_500_error(
    numtracker: NumtrackerClient, httpx_mock: HTTPXMock, nt_query
):
    httpx_mock.add_response(
        method="POST", url=URL, match_json=nt_query, status_code=500, json=EMPTY
    )
    with pytest.raises(
        httpx.HTTPStatusError,
        match="Server error '500 Internal Server Error' for url 'https://numtracker-example.com/graphql'",
    ):
        await numtracker.create_scan("ab123", "p46")


async def test_create_scan_raises_key_error_on_incorrectly_formatted_responses(
    numtracker: NumtrackerClient, httpx_mock: HTTPXMock, nt_query
):
    httpx_mock.add_response(
        method="POST", url=URL, match_json=nt_query, status_code=200, json=EMPTY
    )
    with pytest.raises(
        KeyError,
        match="data",
    ):
        await numtracker.create_scan("ab123", "p46")


async def test_create_scan_raises_runtime_error_on_graphql_error(
    numtracker: NumtrackerClient, httpx_mock: HTTPXMock, nt_query
):
    httpx_mock.add_response(
        method="POST",
        url=URL,
        match_json=nt_query,
        status_code=200,
        json=ERRORS,
    )
    with pytest.raises(RuntimeError, match="Numtracker error:"):
        await numtracker.create_scan("ab123", "p46")

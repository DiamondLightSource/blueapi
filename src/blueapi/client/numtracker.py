import logging
from collections.abc import Mapping
from pathlib import Path
from textwrap import dedent

import requests
from pydantic import Field

from blueapi.utils import BlueapiBaseModel


class DirectoryPath(BlueapiBaseModel):
    """
    Directory location and associated metadata
    """

    instrument: str
    instrument_session: str = Field(alias="instrumentSession")
    path: Path


class ScanPaths(BlueapiBaseModel):
    """
    Description of where to write scan data
    """

    scan_file: str = Field(alias="scanFile")
    scan_number: int = Field(alias="scanNumber")
    directory: DirectoryPath


class NumtrackerScanMutationResponse(BlueapiBaseModel):
    """
    Response from numtracker server when creating a new scan
    """

    scan: ScanPaths


class NumtrackerClient:
    """
    Client for numtracker: https://github.com/DiamondLightSource/numtracker
    Can be used to assign new scan numbers.
    """

    def __init__(
        self,
        url: str,
    ) -> None:
        self._url = url
        self._headers: Mapping[str, str] = {}

    def set_headers(self, headers: Mapping[str, str]) -> None:
        """
        Set default HTTP headers

        Args:
            headers: headers to embed in every request.
        """

        self._headers = headers

    def create_scan(
        self, instrument_session: str, instrument: str
    ) -> NumtrackerScanMutationResponse:
        """
        Create a new scan with numtracker.

        Args:
            instrument_session: The proposal number, proposal code and visit ID
            e.g. cm12345-1

            instrument: The instrument to write data on e.g. i22
        """

        query = {
            "query": dedent(f"""
            mutation{{
                scan(
                    instrument: "{instrument}",
                    instrumentSession: "{instrument_session}"
                    ) {{
                    directory{{
                        instrumentSession
                        instrument
                        path
                    }}
                    scanFile
                    scanNumber
                }}
            }}
            """)
        }

        response = requests.post(
            self._url,
            headers=self._headers,
            json=query,
        )

        response.raise_for_status()
        json = response.json()

        new_collection = NumtrackerScanMutationResponse.model_validate(json["data"])
        logging.debug("New NumtrackerNewScan: %s", new_collection)
        return new_collection

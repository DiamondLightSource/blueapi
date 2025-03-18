import logging
from collections.abc import Mapping
from pathlib import Path
from textwrap import dedent

import requests
from pydantic import Field

from blueapi.utils import BlueapiBaseModel


class DirectoryPath(BlueapiBaseModel):
    instrument: str
    instrument_session: str = Field(alias="instrumentSession")
    path: Path


class ScanPaths(BlueapiBaseModel):
    scan_file: str = Field(alias="scanFile")
    scan_number: int = Field(alias="scanNumber")
    directory: DirectoryPath


class NumtrackerScanMutationResponse(BlueapiBaseModel):
    scan: ScanPaths


class NumtrackerClient:
    def __init__(
        self,
        url: str,
        headers: Mapping[str, str],
    ) -> None:
        self._url = url
        self._headers = headers

    def set_headers(self, pass_through_headers: Mapping[str, str]) -> None:
        self._headers = pass_through_headers

    def create_scan(
        self, instrument_session: str, instrument: str
    ) -> NumtrackerScanMutationResponse:
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

        if json["data"] is not None:
            new_collection = NumtrackerScanMutationResponse.model_validate(json["data"])
            logging.debug("New NumtrackerNewScan: %s", new_collection)
            return new_collection
        else:
            error_message = json.get("errors", "unknown server error")
            raise RuntimeError(error_message)

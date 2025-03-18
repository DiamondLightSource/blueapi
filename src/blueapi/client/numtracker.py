import logging
from collections.abc import Mapping
from pathlib import Path
from textwrap import dedent

import requests
from pydantic import Field

from blueapi.utils import BlueapiBaseModel


class NumtrackerNewScanVisit(BlueapiBaseModel):
    instrument: str
    instrument_session: str = Field(alias="instrumentSession")
    path: Path


class NumtrackerNewScanScan(BlueapiBaseModel):
    scan_file: str = Field(alias="scanFile")
    scan_number: int = Field(alias="scanNumber")
    directory: NumtrackerNewScanVisit


class NumtrackerNewScan(BlueapiBaseModel):
    scan: NumtrackerNewScanScan


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

    # TODO: Could make this async, but since it's called from RE.scan_id_source, we
    # would need to change the RE to accept an async function in the scan_id_source
    # hook. It's a 1-line change but would need to be reviewed etc.
    def create_scan(self, visit: str, beamline: str) -> NumtrackerNewScan:
        query = {
            "query": dedent(f"""
            mutation{{
                scan(instrument: "{beamline}", instrumentSession: "{visit}") {{
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
            new_collection = NumtrackerNewScan.model_validate(json["data"])
            logging.debug("New NumtrackerNewScan: %s", new_collection)
            return new_collection
        else:
            error_message = json.get("errors", "unknown server error")
            raise RuntimeError(error_message)

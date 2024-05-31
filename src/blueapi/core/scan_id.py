import logging
import uuid
from abc import ABC, abstractmethod

import requests
from pydantic import BaseModel


class UniqueScanIdSource(ABC):
    @abstractmethod
    def get_new_scan_id(self) -> int | str:
        """Generate a unique new ID for a run

        Returns:
            int | str: A unique ID for the scan
        """


class UuidScanIdSource(UniqueScanIdSource):
    def get_new_scan_id(self) -> int | str:
        return str(uuid.uuid4())


class GdaNumtrackerResponse(BaseModel):
    """
    Equivalent to a `Scan Number` or `scan_id`, non-globally unique scan identifier.
    Should be always incrementing, unique per-visit, co-ordinated with any other scan engines.
    """

    collectionNumber: int


class GdaScanIdSource(UniqueScanIdSource):
    def __init__(self, url: str) -> None:
        self._url = url
        super().__init__()

    def get_new_scan_id(self) -> int | str:
        response = requests.post(f"{self._url}/numtracker")
        response.raise_for_status()
        gda_response = GdaNumtrackerResponse.parse_obj(response.json())
        return gda_response.collectionNumber


class AggregateScanIdSource(UniqueScanIdSource):
    def __init__(self, sources: list[UniqueScanIdSource]) -> None:
        self._sources = sources
        super().__init__()

    def get_new_scan_id(self) -> int | str:
        for source in self._sources:
            try:
                return source.get_new_scan_id()
            except Exception as ex:
                logging.exception(ex)
        raise ValueError(
            "Could not acquire a valid scan ID from any of the "
            f"following sources: {self._sources}"
        )

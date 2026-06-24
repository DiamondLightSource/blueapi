import logging
from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager, aclosing, nullcontext
from typing import Any, Self

from aiohttp import ClientSession

from blueapi.config import OpaConfig

LOGGER = logging.getLogger(__name__)


class OpaClient:
    def __init__(self, instrument: str, config: OpaConfig):
        LOGGER.info("Creating OpaClient for %s with config %s", instrument, config)
        self._instrument = instrument
        self._config = config
        self._session = ClientSession(base_url=config.root.encoded_string())
        self._audience = config.audience

    async def aclose(self):
        LOGGER.info("Closing OPA session")
        await self._session.close()

    async def _call_opa(self, endpoint: str, data: Mapping[str, Any]) -> bool:
        resp = await self._session.post(
            endpoint,
            json={
                "input": {
                    "beamline": self._instrument,
                    "audience": self._audience,
                    **data,
                }
            },
        )
        return (await resp.json())["result"]

    @classmethod
    def for_config(
        cls, instrument: str | None, config: OpaConfig | None
    ) -> AbstractAsyncContextManager[Self | None]:
        if config:
            if not instrument:
                raise ValueError("Instrument name is required for OPA client")
            return aclosing(cls(instrument, config))
        LOGGER.info("No OPA config provided - not creating OpaClient")
        return nullcontext()

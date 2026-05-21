import logging
from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager, aclosing, nullcontext
from typing import Any, Self

import aiohttp
from aiohttp import ClientSession

from blueapi.config import OpaConfig

LOGGER = logging.getLogger(__name__)


class OpaClient:
    client: aiohttp.ClientSession

    def __init__(self, instrument: str, config: OpaConfig):
        LOGGER.info("Creating OpaClient for %s with config %s", instrument, config)
        self._instrument = instrument
        self._conf = config
        self._session = ClientSession(base_url=config.root.encoded_string())

    async def aclose(self):
        LOGGER.info("Closing OPA session")
        await self._session.close()

    async def _call_opa(self, endpoint, data: Mapping[str, Any]) -> bool:
        try:
            resp = await self._session.post(
                endpoint,
                json={
                    "input": {
                        "beamline": self._instrument,
                        "audience": "account",
                        **data,
                    }
                },
            )
            return (await resp.json())["result"]
        except Exception:
            LOGGER.exception("Failed to run check", exc_info=True)
            raise

    @classmethod
    def for_config(
        cls, instrument: str, config: OpaConfig | None
    ) -> AbstractAsyncContextManager[Self | None]:
        if config:
            return aclosing(cls(instrument, config))
        LOGGER.info("No OPA config provided - not creating OpaClient")
        return nullcontext()


class OpaUserClient:
    client: OpaClient
    token: str

    def __init__(self, client: OpaClient, token: str):
        self.client = client
        self.token = token

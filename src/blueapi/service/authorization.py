import logging
import re
from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager, aclosing, nullcontext
from typing import Any, Self, cast

import aiohttp
from aiohttp import ClientSession
from fastapi import Depends, HTTPException, Request
from starlette import status

from blueapi.config import OIDCConfig, OpaConfig, ServiceAccount
from blueapi.service.authentication import TiledAuth, unchecked_bearer_token
from blueapi.service.model import TaskRequest

LOGGER = logging.getLogger(__name__)
INSTRUMENT_SESSION_RE = re.compile(r"^[a-z]{2}(?P<proposal>\d+)-(?P<visit>\d+)$")


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
        cls, instrument: str | None, config: OpaConfig | None
    ) -> AbstractAsyncContextManager[Self | None]:
        if config:
            if not instrument:
                raise ValueError("Instrument name is required for OPA client")
            return aclosing(cls(instrument, config))
        LOGGER.info("No OPA config provided - not creating OpaClient")
        return nullcontext()

    async def require_tiled_service_account(self, token: str):
        if not await self._call_opa(
            self._conf.tiled_service_account_check,
            {"token": token, "beamline": self._instrument},
        ):
            raise ValueError(
                f"Tiled service account is not valid for '{self._instrument}'"
            )

    async def require_submit_task(self, instrument_session: str, token: str):
        if not (match := INSTRUMENT_SESSION_RE.match(instrument_session)):
            raise ValueError("Invalid instrument session")

        if not await self._call_opa(
            self._conf.submit_task_check,
            {
                "token": token,
                "proposal": int(match["proposal"]),
                "visit": int(match["visit"]),
            },
        ):
            raise HTTPException(status_code=status.HTTP_403_UNORTHORIZED)


class OpaUserClient:
    client: OpaClient
    token: str

    def __init__(self, client: OpaClient, token: str):
        self.client = client
        self.token = token

    async def can_submit_task(self, task: TaskRequest):
        LOGGER.info("Checking permissions to run task")
        await self.client.require_submit_task(task.instrument_session, self.token)


async def validate_tiled_config(
    tiled: ServiceAccount | str | None, oidc: OIDCConfig | None, opa: OpaClient | None
):
    if not isinstance(tiled, ServiceAccount):
        # can't validate an API key
        return

    if not opa or not oidc:
        LOGGER.info("Missing OPA or OIDC configuration required to validate tiled auth")
        return

    LOGGER.info("Validating tiled configuration")
    tiled.token_url = oidc.token_endpoint
    auth = TiledAuth(tiled)
    await opa.require_tiled_service_account(auth.get_access_token())


async def opa(
    request: Request, token: str | None = Depends(unchecked_bearer_token)
) -> OpaUserClient | None:

    if opa := cast(OpaClient | None, getattr(request.app.state, "authz", None)):
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return OpaUserClient(opa, token)
    return None

import logging
from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager, aclosing, nullcontext
from typing import Annotated, Any, Self, cast

import jwt
from aiohttp import ClientSession
from fastapi import Depends, HTTPException
from fastapi.requests import HTTPConnection
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from blueapi.config import OIDCConfig, OpaConfig, ServiceAccount
from blueapi.service.authentication import TiledAuth, unchecked_bearer_token
from blueapi.service.model import TaskRequest
from blueapi.utils import INSTRUMENT_SESSION_RE

LOGGER = logging.getLogger(__name__)

#: Audience that grants a service account write access to tiled
TILED_WRITER_AUDIENCE = "tiled_writer_raw"


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
                    "instrument": self._instrument,
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

    async def require_submit_task(self, instrument_session: str, token: str):
        if not (match := INSTRUMENT_SESSION_RE.match(instrument_session)):
            raise ValueError("Invalid instrument session")

        if not await self._call_opa(
            self._config.submit_task_check,
            {
                "token": token,
                "proposal": int(match["proposal"]),
                "instrument_session": int(match["instrument_session"]),
                "proposal_category": match["category"].upper(),
            },
        ):
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN, detail="Not authorized to submit task"
            )

    async def is_admin(self, token: str) -> bool:
        return await self._call_opa(self._config.admin_check, {"token": token})


class OpaUserClient:
    client: OpaClient
    token: str

    def __init__(self, client: OpaClient, token: str):
        self.client = client
        self.token = token

    async def can_submit_task(self, task: TaskRequest):
        LOGGER.info("Checking permissions to run task")
        await self.client.require_submit_task(task.instrument_session, self.token)

    async def admin(self) -> bool:
        return await self.client.is_admin(self.token)


def require_tiled_service_account(token: str, oidc: OIDCConfig, instrument: str):
    """Check the token is a tiled writer service account for this instrument"""
    signing_key = jwt.PyJWKClient(oidc.jwks_uri).get_signing_key_from_jwt(token)
    try:
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=oidc.id_token_signing_alg_values_supported,
            audience=TILED_WRITER_AUDIENCE,
            issuer=oidc.issuer,
        )
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Tiled service account token is not valid: {e}") from e
    if claims.get("fedid") or claims.get("instrument") != instrument:
        raise ValueError(f"Tiled service account is not valid for '{instrument}'")


async def validate_tiled_config(
    tiled: ServiceAccount | str | None, oidc: OIDCConfig | None, instrument: str | None
):
    if not isinstance(tiled, ServiceAccount):
        # can't validate an API key
        return

    if not oidc or not instrument:
        LOGGER.info(
            "Missing OIDC or instrument configuration required to validate tiled auth"
        )
        return

    LOGGER.info("Validating tiled configuration")
    tiled.token_url = oidc.token_endpoint
    auth = TiledAuth(tiled)
    require_tiled_service_account(auth.get_access_token(), oidc, instrument)


async def opa(
    request: HTTPConnection, token: str | None = Depends(unchecked_bearer_token)
) -> OpaUserClient | None:

    if opa := cast(OpaClient | None, getattr(request.app.state, "authz", None)):
        if not token:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED, detail="Authentication missing"
            )
        return OpaUserClient(opa, token)
    return None


async def submit_permission(
    opa: Annotated[OpaUserClient | None, Depends(opa)],
    task_request: TaskRequest,
):
    if opa:
        await opa.can_submit_task(task_request)

"""
Diamond tiled access policy.

The catalog is laid out as::

    /<instrument>                              tags [instrument]
    /<instrument>/<area>                       tags [instrument]
    /<instrument>/<area>/<proposal>            tags [instrument, proposal]
    /<instrument>/<area>/<proposal>/<session>  tags [instrument, session]
    /<instrument>/<area>/<proposal>/<session>/ tags [instrument, session]

where area is raw or processed, proposal is e.g. CM12345 and session is
e.g. CM12345-1.

Node keys must match their tags: an instrument node is keyed by the instrument,
a proposal node by the proposal and a session node by its session number.

Who can write (create nodes, update metadata, register data) where:
    - super admin: anywhere
    - /, /<instrument>: service account for the instrument
    - /<instrument>/raw/...: service account for the instrument with the
      tiled_writer_raw audience
    - /<instrument>/processed/...: service account for the instrument with the
      tiled_writer_processed audience, or a user with access to the node: any
      session on the instrument for /processed, a session on the proposal for
      /processed/<proposal> and the session itself below that

Proposal and session tags must be ones the writer has access to.

Who can read: super admin everything, otherwise children are filtered at each
level using the OPA session/user_instruments, session/user_proposals and
session/user_sessions rules for the instrument.
"""

import logging
import re
from contextvars import ContextVar
from typing import Any

import httpx
from fastapi import HTTPException
from jose import jwt
from pydantic import HttpUrl
from starlette.status import HTTP_401_UNAUTHORIZED
from tiled.access_control.access_policies import (
    ALL_ACCESS,
    NO_ACCESS,
    AccessPolicy,
)
from tiled.adapters.protocols import BaseAdapter
from tiled.queries import AccessBlobFilter
from tiled.server.schemas import Principal, PrincipalType
from tiled.type_aliases import AccessBlob, AccessTags, Filters, Scopes

logger = logging.getLogger(__name__)

RAW = "raw"
PROCESSED = "processed"
RAW_WRITER_AUDIENCE = "tiled_writer_raw"
PROCESSED_WRITER_AUDIENCE = "tiled_writer_processed"
READ_SCOPES = {"read:metadata", "read:data"}
WRITE_SCOPES = READ_SCOPES | {"write:metadata", "write:data", "create:node", "register"}

PROPOSAL_RE = re.compile(r"^[A-Z]{2}\d+$")
SESSION_RE = re.compile(
    r"^(?P<category>[A-Z]{2})(?P<proposal>\d+)-(?P<instrument_session>\d+)$"
)

#: tiled does not tell init_node where the node is being created, but it always
#: checks allowed_scopes on the parent first, within the same request.
_parent_path: ContextVar[list[str] | None] = ContextVar("parent_path", default=None)


def _check_principal(principal: Principal | None) -> str:
    """Return the access token of an authenticated user"""
    if not isinstance(principal, Principal) or principal.access_token is None:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Principal is None",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if principal.type != PrincipalType.user:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail=f"Principal of type {PrincipalType.user}"
            f" required but given {principal.type}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal.access_token.get_secret_value()


def _claims(token: str) -> dict[str, Any]:
    # The authenticator has already verified the token, so only read its claims
    return jwt.get_unverified_claims(token)


def _is_service_account(
    token: str, instrument: str | None, audiences: set[str]
) -> bool:
    claims = _claims(token)
    aud = claims.get("aud", [])
    aud = {aud} if isinstance(aud, str) else set(aud)
    return (
        not claims.get("fedid")
        and instrument is not None
        and claims.get("instrument") == instrument
        and bool(aud & audiences)
    )


def _tags(access_blob: AccessBlob | None) -> list[str]:
    return list((access_blob or {}).get("tags") or [])


def valid_tags(parent: list[str], key: str | None, tags: list[str]) -> bool:
    """
    True if a node under parent may have these tags. The key is checked too
    when known (it is not when a node is first created).
    """
    match parent:
        case []:
            return len(tags) == 1 and key in (None, tags[0])
        case [instrument]:
            return tags == [instrument] and key in (None, RAW, PROCESSED)
        case [instrument, "raw" | "processed"]:
            return (
                len(tags) == 2
                and tags[0] == instrument
                and bool(PROPOSAL_RE.match(tags[1]))
                and key in (None, tags[1])
            )
        case [instrument, "raw" | "processed", proposal]:
            return (
                len(tags) == 2
                and tags[0] == instrument
                and bool(SESSION_RE.match(tags[1]))
                and tags[1].startswith(f"{proposal}-")
                and key in (None, tags[1].removeprefix(f"{proposal}-"))
            )
        case [instrument, "raw" | "processed", proposal, session, *_]:
            return tags == [instrument, f"{proposal}-{session}"]
    return False


class DiamondOpenPolicyAgentAuthorizationPolicy(AccessPolicy):
    def __init__(
        self,
        authorization_provider: HttpUrl,
        token_audience: str,
        provider: str | None = None,
    ):
        self._authorization_provider = str(authorization_provider)
        self._token_audience = token_audience
        self._provider = provider

    async def _opa(self, rule: str, token: str, **extra: Any) -> Any:
        # ponytail: one OPA request per check, cache per token if this gets slow
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._authorization_provider + rule,
                json={
                    "input": {"token": token, "audience": self._token_audience, **extra}
                },
            )
        response.raise_for_status()
        return response.json().get("result")

    async def _is_admin(self, token: str) -> bool:
        return await self._opa("admin/admin", token) is True

    async def _can_write(self, token: str, path: list[str]) -> bool:
        """True if the token may write to the node at path, or create its children"""
        if await self._is_admin(token):
            return True
        match path:
            case []:
                # Only creates instrument nodes, tags are checked against the claim
                return _is_service_account(
                    token,
                    _claims(token).get("instrument"),
                    {RAW_WRITER_AUDIENCE, PROCESSED_WRITER_AUDIENCE},
                )
            case [instrument]:
                return _is_service_account(
                    token, instrument, {RAW_WRITER_AUDIENCE, PROCESSED_WRITER_AUDIENCE}
                )
            case [instrument, "raw", *_]:
                return _is_service_account(token, instrument, {RAW_WRITER_AUDIENCE})
            case [instrument, "processed", *rest]:
                if _is_service_account(token, instrument, {PROCESSED_WRITER_AUDIENCE}):
                    return True
                if not _claims(token).get("fedid"):
                    return False
                # Users can write processed data where they have access
                match rest:
                    case []:
                        return bool(
                            await self._opa(
                                "session/user_sessions", token, instrument=instrument
                            )
                        )
                    case [proposal]:
                        return await self._has_proposal(token, instrument, proposal)
                    case [proposal, session, *_]:
                        return await self._has_session(
                            token, instrument, f"{proposal}-{session}"
                        )
        return False

    async def _has_proposal(self, token: str, instrument: str, proposal: str) -> bool:
        return proposal in (
            await self._opa("session/user_proposals", token, instrument=instrument)
            or []
        )

    async def _has_session(self, token: str, instrument: str, session: str) -> bool:
        if not (match := SESSION_RE.match(session)):
            return False
        return (
            await self._opa(
                "session/access",
                token,
                proposal=int(match["proposal"]),
                instrument_session=int(match["instrument_session"]),
                proposal_category=match["category"],
                instrument=instrument,
            )
            is True
        )

    async def _check_write(
        self, token: str, parent: list[str], key: str | None, tags: list[str]
    ):
        if not valid_tags(parent, key, tags):
            raise ValueError(
                f"Access tags {tags} are not valid for a node under /{'/'.join(parent)}"
            )
        # A new instrument node is written as that instrument
        path = parent or tags[:1]
        if not await self._can_write(token, path):
            raise ValueError(f"Not permitted to write under /{'/'.join(path)}")
        instrument, ref = tags[0], tags[-1]
        if SESSION_RE.match(ref) and not await self._has_session(
            token, instrument, ref
        ):
            raise ValueError(f"No access to session {ref} on {instrument}")
        if PROPOSAL_RE.match(ref) and not await self._has_proposal(
            token, instrument, ref
        ):
            raise ValueError(f"No access to proposal {ref} on {instrument}")

    async def init_node(
        self,
        principal: Principal,
        authn_access_tags: AccessTags | None,
        authn_scopes: Scopes,
        access_blob: AccessBlob | None = None,
    ) -> tuple[bool, AccessBlob | None]:
        token = _check_principal(principal)
        parent = _parent_path.get()
        if parent is None:
            raise ValueError("Unable to determine where the node is being created")
        tags = _tags(access_blob)
        await self._check_write(token, parent, None, tags)
        return (True, {"tags": tags})

    async def modify_node(
        self,
        node: BaseAdapter,
        principal: Principal,
        authn_access_tags: AccessTags | None,
        authn_scopes: Scopes,
        access_blob: AccessBlob | None,
    ) -> tuple[bool, AccessBlob | None]:
        if access_blob == node.access_blob:  # type: ignore
            return (False, node.access_blob)  # type: ignore
        token = _check_principal(principal)
        path = await _path(node)
        if not path:
            raise ValueError("The root node's access cannot be changed")
        await self._check_write(token, path[:-1], path[-1], _tags(access_blob))
        return (True, access_blob)

    async def filters(
        self,
        node: BaseAdapter,
        principal: Principal,
        authn_access_tags: AccessTags | None,
        authn_scopes: Scopes,
        scopes: Scopes,
    ) -> Filters:
        token = _check_principal(principal)
        if await self._is_admin(token):
            return ALL_ACCESS
        match await _path(node):
            case []:
                tags = await self._opa("session/user_instruments", token)
            case [instrument]:
                tags = [instrument]
            case [instrument, "raw" | "processed"]:
                tags = await self._opa(
                    "session/user_proposals", token, instrument=instrument
                )
            case [instrument, "raw" | "processed", *_]:
                tags = await self._opa(
                    "session/user_sessions", token, instrument=instrument
                )
            case _:
                return NO_ACCESS  # type: ignore
        return [AccessBlobFilter(tags=list(tags or []), user_id=None)]  # type: ignore

    async def allowed_scopes(
        self,
        node: BaseAdapter,
        principal: Principal,
        authn_access_tags: AccessTags | None,
        authn_scopes: Scopes,
    ) -> Scopes:
        path = await _path(node)
        _parent_path.set(path)
        if principal is None or principal.access_token is None:
            return set()
        token = principal.access_token.get_secret_value()
        if await self._is_admin(token):
            return WRITE_SCOPES
        # Node keys cannot be checked on creation, so hide nodes keyed wrongly
        if path and not valid_tags(path[:-1], path[-1], _tags(node.access_blob)):  # type: ignore
            return set()
        if await self._can_write(token, path):
            return WRITE_SCOPES
        return READ_SCOPES


async def _path(node: BaseAdapter) -> list[str]:
    """Keys from the root to this node, the root is []"""
    if path_segments := getattr(node, "path_segments", None):
        return list(await path_segments())
    return []

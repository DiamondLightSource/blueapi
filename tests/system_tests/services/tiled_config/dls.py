import json
import logging

from fastapi import HTTPException
from pydantic import BaseModel, HttpUrl, ValidationError
from starlette.status import (
    HTTP_401_UNAUTHORIZED,
)
from tiled.access_control.access_policies import (
    NO_ACCESS,
    ExternalPolicyDecisionPoint,
    ResultHolder,
)
from tiled.adapters.protocols import BaseAdapter
from tiled.queries import AccessBlobFilter
from tiled.server.schemas import Principal, PrincipalType
from tiled.type_aliases import AccessBlob, AccessTags, Filters, Scopes

logger = logging.getLogger(__name__)


class DiamondAccessBlob(BaseModel):
    """Inputs for the session/access policy, supplied by the client creating a node"""

    proposal: int
    instrument_session: int
    instrument: str
    proposal_category: str

    @property
    def tag(self) -> str:
        """Session reference in the format returned by session/user_sessions"""
        return f"{self.proposal_category}{self.proposal}-{self.instrument_session}"


def _check_principal(principal: Principal | None):
    if not isinstance(principal, Principal):
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


class DiamondOpenPolicyAgentAuthorizationPolicy(ExternalPolicyDecisionPoint):
    def __init__(
        self,
        authorization_provider: HttpUrl,
        token_audience: str,
        create_node_endpoint: str = "session/access",
        allowed_tags_endpoint: str = "session/user_sessions",
        scopes_endpoint: str = "tiled/scopes",
        modify_node_endpoint: str = "session/access",
        empty_access_blob_public: bool = True,
        provider: str | None = None,
    ):
        self._token_audience = token_audience

        super().__init__(
            authorization_provider=authorization_provider,
            create_node_endpoint=create_node_endpoint,
            allowed_tags_endpoint=allowed_tags_endpoint,
            scopes_endpoint=scopes_endpoint,
            provider=provider,
            modify_node_endpoint=modify_node_endpoint,
            empty_access_blob_public=empty_access_blob_public,
        )

    async def init_node(
        self,
        principal: Principal,
        authn_access_tags: AccessTags | None,
        authn_scopes: Scopes,
        access_blob: AccessBlob | None = None,
    ) -> tuple[bool, AccessBlob | None]:
        _check_principal(principal)
        if access_blob is None and self._empty_access_blob_public is not None:
            return self._empty_access_blob_public, access_blob
        decision = await self._get_external_decision(
            self._create_node,
            self.build_input(principal, authn_access_tags, authn_scopes, access_blob),
            ResultHolder[bool],
        )
        if decision and decision.result:
            blob = self._parse_blob(access_blob)
            assert blob is not None  # session/access cannot pass without one
            return (True, {"tags": [blob.tag]})
        raise ValueError("Permission denied not able to add the node")

    async def modify_node(
        self,
        node: BaseAdapter,
        principal: Principal,
        authn_access_tags: AccessTags | None,
        authn_scopes: Scopes,
        access_blob: AccessBlob | None,
    ) -> tuple[bool, AccessBlob | None]:
        _check_principal(principal)
        if access_blob == node.access_blob:  # type: ignore
            logger.info(
                "Node access_blob not modified;"
                f" access_blob is identical: {access_blob}"
            )
            return (False, node.access_blob)  # type: ignore
        decision = await self._get_external_decision(
            self._modify_node,
            self.build_input(principal, authn_access_tags, authn_scopes, access_blob),
            ResultHolder[bool],
        )
        if decision and decision.result:
            blob = self._parse_blob(access_blob)
            assert blob is not None  # session/access cannot pass without one
            return (True, {"tags": [blob.tag]})
        raise ValueError("Permission denied not able to modify the node")

    @staticmethod
    def _parse_blob(access_blob: AccessBlob | None) -> DiamondAccessBlob | None:
        # Client supplied blobs are JSON, stored node tags (e.g. CM12345-1) are not
        if access_blob and access_blob.get("tags"):
            try:
                return DiamondAccessBlob.model_validate_json(access_blob["tags"][0])
            except ValidationError:
                return None
        return None

    def build_input(
        self,
        principal: Principal,
        authn_access_tags: AccessTags | None,
        authn_scopes: Scopes,
        access_blob: AccessBlob | None = None,
    ) -> str:
        _input: dict[str, str | int] = {"audience": self._token_audience}

        if (
            isinstance(principal, Principal)
            and principal.type is PrincipalType.user
            and principal.access_token is not None
        ):
            _input["token"] = principal.access_token.get_secret_value()

        if blob := self._parse_blob(access_blob):
            _input.update(blob.model_dump())

        return json.dumps({"input": _input})

    async def filters(
        self,
        node: BaseAdapter,
        principal: Principal,
        authn_access_tags: AccessTags | None,
        authn_scopes: Scopes,
        scopes: Scopes,
    ) -> Filters:
        _check_principal(principal)
        tags = await self._get_external_decision(
            self._user_tags,
            self.build_input(principal, authn_access_tags, authn_scopes),
            ResultHolder[list[str]],
        )
        if tags is not None:
            return [AccessBlobFilter(tags=tags.result, user_id=None)]  # type: ignore
        else:
            return NO_ACCESS  # type: ignore

import json
import logging

from pydantic import BaseModel, HttpUrl, TypeAdapter
from tiled.access_control.access_policies import (
    ALL_ACCESS,
    NO_ACCESS,
    ExternalPolicyDecisionPoint,
    ResultHolder,
)
from tiled.access_control.scopes import NO_SCOPES
from tiled.adapters.protocols import BaseAdapter
from tiled.queries import AccessBlobFilter
from tiled.server.schemas import Principal, PrincipalType
from tiled.type_aliases import AccessBlob, AccessTags, Filters, Scopes

logger = logging.getLogger(__name__)


class DiamondAccessBlob(BaseModel):
    proposal: int
    visit: int
    beamline: str


class DiamondOpenPolicyAgentAuthorizationPolicy(ExternalPolicyDecisionPoint):
    def __init__(
        self,
        authorization_provider: HttpUrl,
        token_audience: str,
        create_node_endpoint: str = "tiled/user_session",
        allowed_tags_endpoint: str = "tiled/user_sessions",
        scopes_endpoint: str = "tiled/scopes",
        modify_node_endpoint: str = "tiled/modify_session",
        empty_access_blob_public: bool = True,
        provider: str | None = None,
    ):
        self._token_audience = token_audience
        self._type_adapter = TypeAdapter(DiamondAccessBlob)

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
        if access_blob is None and self._empty_access_blob_public is not None:
            return self._empty_access_blob_public, access_blob
        decision = await self._get_external_decision(
            self._create_node,
            self.build_input(principal, authn_access_tags, authn_scopes, access_blob),
            ResultHolder[int],
        )
        if decision and decision.result is not None:
            return (True, {"tags": [decision.result]})
        raise ValueError("Permission denied not able to add the node")

    async def modify_node(
        self,
        node: BaseAdapter,
        principal: Principal,
        authn_access_tags: AccessTags | None,
        authn_scopes: Scopes,
        access_blob: AccessBlob | None,
    ) -> tuple[bool, AccessBlob | None]:
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
        if decision:
            return (decision.result, access_blob)
        raise ValueError("Permission denied not able to add the node")

    def build_input(
        self,
        principal: Principal,
        authn_access_tags: AccessTags | None,
        authn_scopes: Scopes,
        access_blob: AccessBlob | None = None,
    ) -> str:
        _input: dict[str, str | int] = {"audience": self._token_audience}

        if (
            principal.type is PrincipalType.external
            and principal.access_token is not None
        ):
            _input["token"] = principal.access_token.get_secret_value()

        if access_blob is not None and "tags" in access_blob:
            if isinstance(access_blob["tags"][0], str):
                blob = self._type_adapter.validate_json(access_blob["tags"][0])
                _input.update(blob.model_dump())
            elif isinstance(access_blob["tags"][0], int):
                _input["session"] = access_blob["tags"]

        return json.dumps({"input": _input})

    async def filters(
        self,
        node: BaseAdapter,
        principal: Principal,
        authn_access_tags: AccessTags | None,
        authn_scopes: Scopes,
        scopes: Scopes,
    ) -> Filters:
        tags = await self._get_external_decision(
            self._user_tags,
            self.build_input(principal, authn_access_tags, authn_scopes),
            ResultHolder[list[int | str]],
        )
        if tags is not None:
            if tags.result == ["*"]:
                return ALL_ACCESS  # type: ignore
            return [AccessBlobFilter(tags=tags.result, user_id=None)]  # type: ignore
        else:
            return NO_ACCESS  # type: ignore

    async def allowed_scopes(
        self,
        node: BaseAdapter,
        principal: Principal,
        authn_access_tags: AccessTags | None,
        authn_scopes: Scopes,
    ) -> Scopes:
        scopes = await self._get_external_decision(
            self._node_scopes,
            self.build_input(
                principal,
                authn_access_tags,
                authn_scopes,
                getattr(node, "access_blob", None),
            ),
            ResultHolder[set[str]],
        )
        if scopes:
            return scopes.result
        return NO_SCOPES

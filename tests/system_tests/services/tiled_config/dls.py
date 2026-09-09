import json
import logging

from fastapi import HTTPException
from pydantic import BaseModel, HttpUrl, TypeAdapter, ValidationError
from starlette.status import (
    HTTP_401_UNAUTHORIZED,
)
from tiled.access_control.access_policies import (
    ALL_ACCESS,
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
    beamline: str
    # The full proposal code, e.g. "cm12345" - tiled.rego strips the leading
    # letters itself where it needs the bare number.
    proposal: str | None = None
    visit: int | None = None


# Maps a composite access tag's "key" (as produced by tiled.rego's
# beamline_tag/proposal_tag/session_tag, e.g.
# "beamline:i22,proposal:cm111,session:cm111-1") to the corresponding OPA
# input field. All of these are strings on an existing node's tag - "session"
# here is the full "cm111-1" instrument session, not the internal numeric
# session id used by modify_session, so it's kept under its own field name
# rather than aliased to "visit".
_TAG_KEY_TO_INPUT_FIELD = {
    "beamline": "beamline",
    "proposal": "proposal",
    "session": "session",
}


def _parse_composite_tag(tag: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in tag.split(","):
        key, _, value = part.partition(":")
        field = _TAG_KEY_TO_INPUT_FIELD.get(key)
        if field is not None:
            fields[field] = value
    return fields


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
        create_node_endpoint: str = "tiled/user_session",
        allowed_tags_endpoint: str = "tiled/user_sessions",
        scopes_endpoint: str = "tiled/scopes",
        modify_node_endpoint: str = "tiled/modify_session",
        provider: str | None = None,
    ):
        self._token_audience = token_audience
        self._type_adapter = TypeAdapter(DiamondAccessBlob | int)

        super().__init__(
            authorization_provider=authorization_provider,
            create_node_endpoint=create_node_endpoint,
            allowed_tags_endpoint=allowed_tags_endpoint,
            scopes_endpoint=scopes_endpoint,
            provider=provider,
            modify_node_endpoint=modify_node_endpoint,
        )

    async def init_node(
        self,
        principal: Principal,
        authn_access_tags: AccessTags | None,
        authn_scopes: Scopes,
        access_blob: AccessBlob | None = None,
    ) -> tuple[bool, AccessBlob | None]:
        _check_principal(principal)
        decision = await self._get_external_decision(
            self._create_node,
            self.build_input(principal, authn_access_tags, authn_scopes, access_blob),
            ResultHolder[str],
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
            isinstance(principal, Principal)
            and principal.type is PrincipalType.user
            and principal.access_token is not None
        ):
            _input["token"] = principal.access_token.get_secret_value()

        if (
            access_blob is not None
            and "tags" in access_blob
            and len(access_blob["tags"]) > 0
        ):
            tag = access_blob["tags"][0]
            try:
                blob = self._type_adapter.validate_json(tag)
            except ValidationError:
                # Not a create-request JSON blob - it's a composite tag
                # already assigned to an existing node (e.g. tiled checking
                # scopes on a parent before creating a child).
                blob = None
                _input.update(_parse_composite_tag(tag))
            if isinstance(blob, DiamondAccessBlob):
                _input.update(blob.model_dump(exclude_none=True))
            elif isinstance(blob, int):
                _input["session"] = str(blob)

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
            if tags.result == ["*"]:
                return ALL_ACCESS
            return [AccessBlobFilter(tags=tags.result, user_id=None)]  # type: ignore
        else:
            return NO_ACCESS  # type: ignore

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Annotated, Any

import httpx
import jwt
from authlib.integrations.requests_client import OAuth2Session
from fastapi import Depends, HTTPException
from fastapi.requests import HTTPConnection
from fastapi.security.utils import get_authorization_scheme_param
from starlette.status import HTTP_401_UNAUTHORIZED

# Re-exported for backwards compatibility, these now live in blueapi.client.session
from blueapi.client.session import (  # noqa: F401
    CacheManager,
    JWTAuth,
    SessionCacheManager,
    SessionManager,
)
from blueapi.config import OIDCConfig, ServiceAccount


class TiledAuth(httpx.Auth):
    def __init__(self, tiled_auth: ServiceAccount):
        if tiled_auth.token_url == "":
            raise RuntimeError("Token URL is not set please check oidc config")
        self._client = OAuth2Session(
            tiled_auth.client_id,
            tiled_auth.client_secret.get_secret_value(),
            token_endpoint=tiled_auth.token_url,
            token_endpoint_auth_method="client_secret_post",
            grant_type="client_credentials",
        )
        self._sync_lock = threading.RLock()

    requires_request_body = True  # body is replayed on the 401 retry

    def get_access_token(self, stale: str | None = None) -> str:
        """Cached client_credentials token, re-fetched when expired or rejected"""
        with self._sync_lock:
            token = self._client.token
            if (
                not token
                or token["access_token"] == stale
                # is_expired() is None when the IdP sends no expiry: don't cache
                or token.is_expired(leeway=self._client.leeway) is not False
            ):
                token = self._client.fetch_token()
            return token["access_token"]

    def sync_auth_flow(self, request):
        access_token = self.get_access_token()
        request.headers["Authorization"] = f"Bearer {access_token}"
        response = yield request
        if response.status_code == HTTP_401_UNAUTHORIZED:
            # Revoked or keys rotated before expiry: fetch a new token, retry once.
            # stale= stops concurrent 401s each fetching their own replacement.
            new_token = self.get_access_token(stale=access_token)
            request.headers["Authorization"] = f"Bearer {new_token}"
            yield request


def unchecked_bearer_token(req: HTTPConnection) -> str | None:
    """Get bearer token value from authorization header"""

    auth_header = req.headers.get("Authorization")
    auth_cookie = req.cookies.get("Authorization")

    # This is an abridged version of the same feature of
    # OAuth2AuthorizationCodeBearer from fastapi. Replicating here prevents
    # passing unused configuration and means the schema does not include auth
    # details for servers that do not support it.
    scheme, param = get_authorization_scheme_param(auth_header or auth_cookie)
    if scheme.casefold() != "bearer":
        return None
    return param.strip()


UncheckedBearerToken = Annotated[str | None, Depends(unchecked_bearer_token)]


def build_access_token_check(config: OIDCConfig):
    """
    Create a function to validate the bearer token of requests

    The returned function should be used via fastAPI's 'Depends' mechanism to
    ensure users are authenticated
    """
    jwkclient = jwt.PyJWKClient(config.jwks_uri)

    def validate_bearer_token(request: HTTPConnection, token: UncheckedBearerToken):
        """Check that a bearer token is valid and inject into request state"""
        if not token:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )

        signing_key = jwkclient.get_signing_key_from_jwt(token)
        decoded: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=config.id_token_signing_alg_values_supported,
            verify=True,
            audience=config.client_audience,
            issuer=config.issuer,
        )
        request.state.decoded_access_token = decoded

    return validate_bearer_token


def access_token(request: HTTPConnection) -> Mapping[str, Any] | None:
    """Get the decoded and verified access token of the user making the request"""
    return getattr(request.state, "decoded_access_token", None)


def fedid(
    access_token: Annotated[Mapping[str, Any] | None, Depends(access_token)],
) -> str | None:
    return access_token.get("fedid") if access_token else None


Fedid = Annotated[str | None, Depends(fedid)]

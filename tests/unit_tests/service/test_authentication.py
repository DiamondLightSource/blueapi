from unittest.mock import Mock, patch

import httpx
import jwt
import pytest
import responses
import respx
from fastapi import HTTPException
from pydantic import SecretStr
from starlette.status import HTTP_200_OK

from blueapi.config import OIDCConfig, ServiceAccount
from blueapi.service import authentication
from blueapi.service.authentication import (
    TiledAuth,
    access_token,
    build_access_token_check,
    unchecked_bearer_token,
)


def test_server_raises_exception_for_invalid_token(
    oidc_config: OIDCConfig, mock_authn_server: responses.RequestsMock
):
    inner = authentication.build_access_token_check(oidc_config)
    with pytest.raises(jwt.PyJWTError):
        inner(Mock(), token="Invalid Token")


def test_processes_valid_token(
    oidc_config: OIDCConfig,
    mock_authn_server: responses.RequestsMock,
    valid_token_with_jwt,
):
    inner = authentication.build_access_token_check(oidc_config)
    inner(Mock(), token=valid_token_with_jwt["access_token"])


@pytest.mark.parametrize(
    "header,cookie,token",
    [
        (None, None, None),
        ("", None, None),
        ("ApiKey foobar", None, None),
        ("Bearer foobar", None, "foobar"),
        ("Bearer   with_whitespace   ", None, "with_whitespace"),
        ("Bearerfoobar", None, None),
        (None, "Bearer foobar", "foobar"),
        ("", "Bearer foo", "foo"),
        ("Bearer foo", "bearer bar", "foo"),
    ],
)
def test_unchecked_bearer_token(
    header: str | None, cookie: str | None, token: str | None
):
    req = Mock(headers={"Authorization": header}, cookies={"Authorization": cookie})
    assert unchecked_bearer_token(req) == token


def test_access_token():
    req = Mock()
    req.state.decoded_access_token = {"foo": "bar"}

    assert access_token(req) == {"foo": "bar"}


def test_access_token_without_token():
    req = Mock()
    del req.state.decoded_access_token

    assert access_token(req) is None


@patch("blueapi.service.authentication.jwt")
def test_build_access_token(mock_jwt: Mock):
    # Return None when building client to ensure no field/method access
    mock_jwt.PyJWKClient.return_value = None
    oidc_config = Mock()
    req = Mock()

    validate_fn = build_access_token_check(oidc_config)

    with pytest.raises(HTTPException, match="401"):
        validate_fn(req, token=None)

    mock_jwt.decode.assert_not_called()


def test_tiled_auth_raises_exception():
    with pytest.raises(
        RuntimeError, match="Token URL is not set please check oidc config"
    ):
        auth = ServiceAccount()
        TiledAuth(tiled_auth=auth)


@respx.mock
def test_tiled_auth_sync_auth_flow():
    client_id = "client"
    client_secret = SecretStr("secret")
    token_url = "http://keycloak.com/token"
    access_token = "access_token"

    respx.post(token_url).mock(
        return_value=httpx.Response(
            status_code=HTTP_200_OK, json={"access_token": access_token}
        )
    )

    tiled_auth = TiledAuth(
        tiled_auth=ServiceAccount(
            client_id=client_id,
            client_secret=client_secret,
            token_url=token_url,
        )
    )

    request = Mock()
    request.headers = {}

    flow = tiled_auth.sync_auth_flow(request)
    result = next(flow)

    assert result.headers["Authorization"] == f"Bearer {access_token}"

import os
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import httpx
import jwt
import pytest
import responses
import respx
from fastapi import HTTPException
from pydantic import SecretStr
from starlette.status import HTTP_200_OK, HTTP_403_FORBIDDEN

from blueapi.config import OIDCConfig, ServiceAccount
from blueapi.service import authentication
from blueapi.service.authentication import (
    SessionCacheManager,
    SessionManager,
    TiledAuth,
    access_token,
    build_access_token_check,
    unchecked_bearer_token,
)


@pytest.fixture
def auth_token_path(tmp_path) -> Path:
    return tmp_path / "blueapi_cache"


@pytest.fixture
def session_manager(
    oidc_config: OIDCConfig,
    auth_token_path,
    mock_authn_server: responses.RequestsMock,
) -> SessionManager:
    return SessionManager(
        server_config=oidc_config, cache_manager=SessionCacheManager(auth_token_path)
    )


def test_logout(
    session_manager: SessionManager,
    oidc_config: OIDCConfig,
    cached_valid_token: Path,
    auth_token_path: Path,
):
    assert os.path.exists(auth_token_path)
    session_manager.logout()
    assert not os.path.exists(auth_token_path)


def test_refresh_auth_token(
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    cached_valid_refresh: Path,
):
    token = session_manager.get_valid_access_token()
    assert token == "new_token"


def test_get_empty_token_if_no_cache(session_manager: SessionManager):
    token = session_manager.get_valid_access_token()
    assert token == ""


def test_get_empty_token_if_refresh_fails(
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    cached_expired_refresh: Path,
):
    assert cached_expired_refresh.exists()
    token = session_manager.get_valid_access_token()
    assert token == ""
    assert not cached_expired_refresh.exists()


def test_get_empty_token_if_invalid_cache(
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    cache_with_invalid_audience: Path,
):
    token = session_manager.get_valid_access_token()
    assert token == ""


def test_get_empty_token_if_exception_in_decode(
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    cached_expired_refresh: Path,
):
    assert cached_expired_refresh.exists()
    token = session_manager.get_valid_access_token()
    assert token == ""
    assert not cached_expired_refresh.exists()


def test_poll_for_token(
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    valid_token: dict[str, Any],
    device_code: str,
):
    token = session_manager.poll_for_token(device_code, 1, 2)
    assert token == valid_token


@patch("blueapi.service.authentication.time.sleep", return_value=None)
def test_poll_for_token_timeout(
    mock_sleep,
    oidc_well_known: dict[str, Any],
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    device_code: str,
):
    mock_authn_server.stop()
    mock_authn_server.remove(responses.POST, oidc_well_known["token_endpoint"])
    mock_authn_server.post(
        url=oidc_well_known["token_endpoint"],
        json={"error": "authorization_pending"},
        status=HTTP_403_FORBIDDEN,
    )
    with pytest.raises(TimeoutError), mock_authn_server:
        session_manager.poll_for_token(device_code, 0.01, 0.01)


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


def test_session_cache_manager_returns_writable_file_path(tmp_path):
    os.environ["XDG_CACHE_HOME"] = str(tmp_path)
    cache = SessionCacheManager(token_path=None)
    Path(cache._file_path).touch()
    assert os.path.isfile(cache._file_path)
    assert cache._file_path == f"{tmp_path}/blueapi_cache"


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
    assert unchecked_bearer_token(header, cookie) == token


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

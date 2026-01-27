import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import jwt
import pytest
import responses
import respx
from pydantic import HttpUrl, SecretStr
from starlette.status import HTTP_403_FORBIDDEN

from blueapi.config import OIDCConfig, TiledConfig
from blueapi.service import main
from blueapi.service.authentication import (
    SessionCacheManager,
    SessionManager,
    TiledAuth,
    Token,
    TokenType,
)


@pytest.fixture
def auth_token_path(tmp_path: Path) -> Path:
    return tmp_path / "blueapi_cache"


@pytest.fixture
def session_manager(
    oidc_config: OIDCConfig,
    auth_token_path: Path,
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
    inner = main.verify_access_token(oidc_config)
    with pytest.raises(jwt.PyJWTError):
        inner(access_token="Invalid Token")


def test_processes_valid_token(
    oidc_config: OIDCConfig,
    mock_authn_server: responses.RequestsMock,
    valid_token_with_jwt: dict[str, Any],
):
    inner = main.verify_access_token(oidc_config)
    inner(access_token=valid_token_with_jwt["access_token"])


def test_session_cache_manager_returns_writable_file_path(tmp_path: Path):
    os.environ["XDG_CACHE_HOME"] = str(tmp_path)
    cache = SessionCacheManager(token_path=None)
    Path(cache._file_path).touch()
    assert os.path.isfile(cache._file_path)
    assert cache._file_path == f"{tmp_path}/blueapi_cache"


@pytest.fixture
def token_exchange_response():
    return {
        "access_token": "token-exchange-access-token",
        "expires_in": 900,
        "issued_token_type": "urn:ietf:params:oauth:token-type:refresh_token",
        "not-before-policy": 0,
        "refresh_expires_in": 1800,
        "refresh_token": "token-exchange-refresh-token",
        "scope": "openid profile email fedid",
        "session_state": "c1311c2b-a4e1-456b-2ff7-9f0a7e2f516b",
        "token_type": "Bearer",
    }


@pytest.fixture
def refresh_token_response():
    return {
        "access_token": "new-access-token",
        "expires_in": 900,
        "refresh_expires_in": 1800,
        "refresh_token": "token-exchange-refresh-token",
        "not-before-policy": 0,
        "session_state": "c1311c2b-a4e1-406b-9ff7-9f0a7e2f516b",
        "scope": "openid profile email fedid",
    }


@pytest.fixture
def tiled_url() -> str:
    return "http://tiled.com"


@pytest.fixture
def blueapi_jwt():
    return "blueapi-token"


@pytest.fixture
def tiled_config(oidc_config: OIDCConfig, mock_authn_server, tiled_url: str):
    return TiledConfig(
        enabled=True,
        url=HttpUrl(tiled_url),
        token_url=oidc_config.token_endpoint,
        token_exchange_client_id="token_exchange_id",
        token_exchange_secret=SecretStr("secret"),
    )


@pytest.fixture()
def tiled_auth(tiled_config, blueapi_jwt):
    return TiledAuth(
        tiled_config=tiled_config,
        blueapi_jwt_token=blueapi_jwt,
    )


@pytest.fixture
def mock_token_exchange(
    oidc_config: OIDCConfig,
    token_exchange_response,
    refresh_token_response,
    tiled_config,
    blueapi_jwt,
):
    token_exchange_data = {
        "client_id": tiled_config.token_exchange_client_id,
        "client_secret": tiled_config.token_exchange_secret.get_secret_value(),
        "subject_token": blueapi_jwt,
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "requested_token_type": "urn:ietf:params:oauth:token-type:refresh_token",
    }
    token_exchange_refresh_data = {
        "client_id": tiled_config.token_exchange_client_id,
        "client_secret": tiled_config.token_exchange_secret.get_secret_value(),
        "grant_type": "refresh_token",
        "refresh_token": token_exchange_response["refresh_token"],
    }
    with responses.RequestsMock(assert_all_requests_are_fired=False) as requests_mock:
        requests_mock.post(
            oidc_config.token_endpoint,
            # name="exchange_tokens",
            match=[responses.matchers.urlencoded_params_matcher(token_exchange_data)],
            json=token_exchange_response,
        )
        # Refresh token
        requests_mock.post(
            oidc_config.token_endpoint,
            # name="refresh_tokens",
            match=[
                responses.matchers.urlencoded_params_matcher(
                    token_exchange_refresh_data
                )
            ],
            json=refresh_token_response,
        )

        yield requests_mock


@respx.mock
def test_blueapi_token_exchange(
    tiled_auth: TiledAuth, tiled_url: str, mock_token_exchange
):
    respx.get(tiled_url).mock(side_effect=[httpx.Response(200), httpx.Response(200)])
    with httpx.Client(auth=tiled_auth) as tiled_client:
        tiled_client.get(tiled_url)
        # assert mock_token_exchange["exchange_tokens"].called
        # assert not mock_token_exchange["refresh_tokens"].called
        tiled_client.get(tiled_url)


@respx.mock
def test_blueapi_token_exchange_refresh_token(
    tiled_auth: TiledAuth, tiled_url: str, mock_token_exchange
):
    respx.get(tiled_url).mock(
        side_effect=[httpx.Response(200), httpx.Response(401), httpx.Response(200)]
    )
    with httpx.Client(auth=tiled_auth) as tiled_client:
        tiled_client.get(tiled_url)
        # assert mock_token_exchange["exchange_tokens"].called
        # assert not mock_token_exchange["refresh_tokens"].called
        # Make access token expired
        tiled_auth._access_token = MagicMock()
        tiled_auth._access_token.expired = True
        tiled_client.get(tiled_url)
        # assert mock_token_exchange["refresh_tokens"].called


# @respx.mock
def test_blueapi_token_exchange_refresh_token_exception(
    tiled_auth: TiledAuth, tiled_url: str, mock_token_exchange
):
    respx.get(tiled_url).mock(
        side_effect=[httpx.Response(200), httpx.Response(401), httpx.Response(200)]
    )
    with httpx.Client(auth=tiled_auth) as tiled_client:
        tiled_client.get(tiled_url)
        # assert mock_token_exchange["exchange_tokens"].called
        # assert not mock_token_exchange["refresh_tokens"].called
        # Make access token expired
        tiled_auth._access_token = MagicMock()
        tiled_auth._access_token.expired = True
        # Make refresh token None
        tiled_auth._refresh_token = None
        with pytest.raises(
            Exception, match="Cannot refresh session as no refresh token available"
        ):
            tiled_client.get(tiled_url)
        # assert not mock_token_exchange["refresh_tokens"].called


def test_token_is_assumed_valid_if_information_not_available():
    access_token = Token(
        token_dict={"access_token": "foo", "refresh_token": "bar"},
        token_type=TokenType.access_token,
    )
    assert not access_token.expired


def test_token_raise_value_error_if_not_found():
    with pytest.raises(
        ValueError, match=f"Not able to find {TokenType.access_token} in response"
    ):
        Token(token_dict={"refresh_token": "bar"}, token_type=TokenType.access_token)

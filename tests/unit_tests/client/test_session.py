import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import requests
import responses
from authlib.integrations.requests_client import OAuthError
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_503_SERVICE_UNAVAILABLE,
)

from blueapi.client.session import SessionCacheManager, SessionManager
from blueapi.config import OIDCConfig


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


@patch("blueapi.client.session.time.sleep", return_value=None)
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


def _token_endpoint_replies(
    mock_authn_server: responses.RequestsMock, url: str, *replies: dict[str, Any]
) -> None:
    """Replace the token endpoint with replies served in order"""
    mock_authn_server.stop()
    mock_authn_server.remove(responses.POST, url)
    for reply in replies:
        mock_authn_server.post(url=url, **reply)


@patch("blueapi.client.session.time.sleep", return_value=None)
@pytest.mark.parametrize(
    "first_reply,expected_sleep",
    [
        ({"json": {"error": "slow_down"}, "status": HTTP_400_BAD_REQUEST}, 6),
        ({"body": "Service Unavailable", "status": HTTP_503_SERVICE_UNAVAILABLE}, 1),
        ({"body": "<html>rate limited</html>", "status": 429}, 1),
    ],
)
def test_poll_for_token_keeps_polling_after_retryable_reply(
    mock_sleep,
    first_reply: dict[str, Any],
    expected_sleep: float,
    oidc_well_known: dict[str, Any],
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    valid_token: dict[str, Any],
    device_code: str,
):
    _token_endpoint_replies(
        mock_authn_server,
        oidc_well_known["token_endpoint"],
        first_reply,
        {"json": valid_token},
    )
    with mock_authn_server:
        assert session_manager.poll_for_token(device_code, 1, 60) == valid_token
    mock_sleep.assert_called_once_with(expected_sleep)


@pytest.mark.parametrize("error", ["access_denied", "expired_token"])
def test_poll_for_token_raises_on_terminal_error(
    error: str,
    oidc_well_known: dict[str, Any],
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    device_code: str,
):
    _token_endpoint_replies(
        mock_authn_server,
        oidc_well_known["token_endpoint"],
        {"json": {"error": error}, "status": HTTP_400_BAD_REQUEST},
    )
    with pytest.raises(OAuthError, match=error), mock_authn_server:
        session_manager.poll_for_token(device_code, 1, 60)


def test_refresh_network_error_keeps_cache(
    oidc_well_known: dict[str, Any],
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    cached_valid_refresh: Path,
):
    _token_endpoint_replies(
        mock_authn_server,
        oidc_well_known["token_endpoint"],
        {"body": requests.ConnectionError("unreachable")},
    )
    with pytest.raises(requests.ConnectionError), mock_authn_server:
        session_manager.get_valid_access_token()
    assert cached_valid_refresh.exists()


def test_session_cache_manager_returns_writable_file_path(tmp_path):
    os.environ["XDG_CACHE_HOME"] = str(tmp_path)
    cache = SessionCacheManager(token_path=None)
    Path(cache._file_path).touch()
    assert os.path.isfile(cache._file_path)
    assert cache._file_path == f"{tmp_path}/blueapi_cache"

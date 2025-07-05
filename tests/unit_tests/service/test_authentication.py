from pathlib import Path
from typing import Any
from unittest.mock import patch

import jwt
import pytest
import responses
from starlette.status import HTTP_403_FORBIDDEN

from blueapi.config import OIDCConfig
from blueapi.service import main
from blueapi.service.authentication import SessionManager
from blueapi.utils.caching import DiskCache


@pytest.fixture
def auth_token_path(tmp_path: Path) -> Path:
    return tmp_path / "blueapi_cache.d" / "auth_token"


@pytest.fixture
def session_manager(
    oidc_config: OIDCConfig,
    tmp_path: Path,
    mock_authn_server: responses.RequestsMock,
) -> SessionManager:
    return SessionManager(
        server_config=oidc_config,
        cache_manager=DiskCache(tmp_path),
    )


def test_logout(
    session_manager: SessionManager,
    oidc_config: OIDCConfig,
    cached_valid_token: DiskCache,
    auth_token_path: Path,
):
    assert "auth_token" in cached_valid_token
    session_manager.logout()
    assert "auth_token" not in cached_valid_token


def test_refresh_auth_token(
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    cached_valid_refresh: DiskCache,
):
    token = session_manager.get_valid_access_token()
    assert token == "new_token"


def test_get_empty_token_if_no_cache(session_manager: SessionManager):
    token = session_manager.get_valid_access_token()
    assert token == ""


def test_get_empty_token_if_refresh_fails(
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    cached_expired_refresh: DiskCache,
):
    assert "auth_token" in cached_expired_refresh
    token = session_manager.get_valid_access_token()
    assert token == ""
    assert "auth_token" not in cached_expired_refresh


def test_get_empty_token_if_invalid_cache(
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    cache_with_invalid_audience: DiskCache,
):
    token = session_manager.get_valid_access_token()
    assert token == ""


def test_get_empty_token_if_exception_in_decode(
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    cached_expired_refresh: DiskCache,
):
    assert "auth_token" in cached_expired_refresh
    token = session_manager.get_valid_access_token()
    assert token == ""
    assert "auth_token" not in cached_expired_refresh


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
    valid_token_with_jwt,
):
    inner = main.verify_access_token(oidc_config)
    inner(access_token=valid_token_with_jwt["access_token"])

import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import responses
from starlette.status import HTTP_403_FORBIDDEN

from blueapi.config import CLIClientConfig, OIDCConfig
from blueapi.service.authentication import SessionManager


@pytest.fixture
def session_manager(oidc_config: OIDCConfig) -> SessionManager:
    return SessionManager(oidc_config)


def test_logout(
    session_manager: SessionManager,
    oidc_config: CLIClientConfig,
    cached_valid_token: Path,
):
    assert os.path.exists(oidc_config.token_path)
    session_manager.logout()
    assert not os.path.exists(oidc_config.token_path)


def test_refresh_auth_token(
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    cached_expired_token: Path,
):
    token = session_manager.get_token()
    assert token and token["access_token"] == "expired_token"

    session_manager.refresh_auth_token()
    token = session_manager.get_token()
    assert token and token["access_token"] == "new_token"


def test_poll_for_token(
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    valid_token: dict[str, Any],
    device_code: str,
):
    token = session_manager.poll_for_token(device_code, 1, 2)
    assert token == valid_token


@patch("time.sleep")
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
        session_manager.poll_for_token(device_code, 1, 2)

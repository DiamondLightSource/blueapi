import os
from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import responses
from fastapi.exceptions import HTTPException
from starlette.status import HTTP_403_FORBIDDEN

from blueapi.config import CLIClientConfig, OIDCConfig
from blueapi.service import main
from blueapi.service.authentication import SessionManager


@pytest.fixture
def session_manager(oidc_config: OIDCConfig) -> SessionManager:
    return SessionManager(oidc_config)


def test_logout(
    session_manager: SessionManager,
    oidc_config: CLIClientConfig,
    cached_valid_token: Path,
):
    assert os.path.exists(oidc_config.token_file_path)
    session_manager.logout()
    assert not os.path.exists(oidc_config.token_file_path)


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
    valid_oidc_config: dict[str, Any],
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    device_code: str,
):
    mock_authn_server.stop()
    mock_authn_server.remove(responses.POST, valid_oidc_config["token_endpoint"])
    mock_authn_server.post(
        url=valid_oidc_config["token_endpoint"],
        json={"error": "authorization_pending"},
        status=HTTP_403_FORBIDDEN,
    )
    with pytest.raises(TimeoutError), mock_authn_server:
        session_manager.poll_for_token(device_code, 1, 2)


def test_valid_token_access_granted(
    oidc_config: OIDCConfig,
    mock_authn_server: responses.RequestsMock,
    valid_token: dict[str, Any],
):
    main.verify_access_token(oidc_config)(valid_token["id_token"])


def test_invalid_token_no_access(
    oidc_config: OIDCConfig,
    mock_authn_server: responses.RequestsMock,
):
    with pytest.raises(HTTPException) as exec, mock_authn_server:
        main.verify_access_token(oidc_config)("bad_token")
    assert exec.value.status_code == HTTPStatus.UNAUTHORIZED


def test_expired_token_no_access(
    oidc_config: OIDCConfig,
    mock_authn_server: responses.RequestsMock,
    expired_token: dict[str, Any],
):
    with pytest.raises(HTTPException) as exec, mock_authn_server:
        main.verify_access_token(oidc_config)(expired_token["id_token"])
    assert exec.value.status_code == HTTPStatus.UNAUTHORIZED

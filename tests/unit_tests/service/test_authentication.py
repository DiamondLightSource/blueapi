import base64
import os
from collections.abc import Callable
from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import responses
from fastapi.exceptions import HTTPException
from starlette.status import HTTP_403_FORBIDDEN

from blueapi.config import CLIClientConfig, OAuthClientConfig, OIDCConfig
from blueapi.service import main
from blueapi.service.authentication import SessionManager


@pytest.fixture
def configure_refreshed_token(mock_authn_server: responses.RequestsMock):
    mock_authn_server.post(
        url="https://example.com/token",
        json={"access_token": "new_access_token"},
    )

    return mock_authn_server


@pytest.fixture
def configure_device_flow_token(mock_authn_server: responses.RequestsMock):
    mock_authn_server.post(
        url="https://example.com/device_authorization",
        json={"expires_in": 30, "interval": 5, "device_code": "device_code"},
    )
    mock_authn_server.post(
        url="https://example.com/token",
        json={"access_token": "access_token"},
    )

    return mock_authn_server


@pytest.fixture
def configure_awaiting_token(mock_authn_server: responses.RequestsMock):
    mock_authn_server.post(
        url="https://example.com/token",
        json={"error": "authorization_pending"},
        status=HTTP_403_FORBIDDEN,
    )

    return mock_authn_server


@pytest.fixture
def expired_token(tmp_path: Path):
    token_path = tmp_path / "token"
    with open(token_path, "w") as token_file:
        # base64 encoded token
        token_file.write(
            base64.b64encode(
                b'{"access_token":"expired_token","refresh_token":"refresh_token"}'
            ).decode("utf-8")
        )
    yield token_path


@pytest.fixture
def client_config(tmp_path: Path) -> OAuthClientConfig:
    return CLIClientConfig(
        client_id="client_id",
        client_audience="client_audience",
        token_file_path=tmp_path / "token",
    )


@pytest.fixture
def server_config(valid_oidc_url: str, mock_authn_server) -> OIDCConfig:
    return OIDCConfig(well_known_url=valid_oidc_url)


@pytest.fixture
def session_manager(
    client_config: OAuthClientConfig, server_config: OIDCConfig
) -> SessionManager:
    return SessionManager(server_config, client_config)


@pytest.fixture
def connected_client_config(client_config: OAuthClientConfig) -> CLIClientConfig:
    assert isinstance(client_config, CLIClientConfig)
    with open(client_config.token_file_path, "w") as token_file:
        # base64 encoded token
        token_file.write(
            base64.b64encode(
                b'{"access_token":"token","refresh_token":"refresh_token"}'
            ).decode("utf-8")
        )
    return client_config


def test_logout(
    session_manager: SessionManager, connected_client_config: CLIClientConfig
):
    assert os.path.exists(connected_client_config.token_file_path)
    session_manager.logout()
    assert not os.path.exists(connected_client_config.token_file_path)


def test_refresh_auth_token(
    configure_refreshed_token: responses.RequestsMock,
    session_manager: SessionManager,
    expired_token: Path,
):
    token = session_manager.get_token()
    assert token and token["access_token"] == "expired_token"

    with configure_refreshed_token:
        session_manager.refresh_auth_token()
    token = session_manager.get_token()
    assert token and token["access_token"] == "new_access_token"


def test_poll_for_token(
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
):
    mock_authn_server.post(
        url="https://example.com/token",
        json={"access_token": "access_token"},
    )
    with mock_authn_server:
        token = session_manager.poll_for_token("device_code", 1, 2)
    assert token == {"access_token": "access_token"}


@patch("time.sleep")
def test_poll_for_token_timeout(
    mock_sleep,
    configure_awaiting_token,
    session_manager: SessionManager,
):
    with pytest.raises(TimeoutError), configure_awaiting_token:
        session_manager.poll_for_token("device_code", 1, 2)


def test_valid_token_access_granted(
    server_config: OIDCConfig,
    mock_authn_server: responses.RequestsMock,
):
    with mock_authn_server:
        main.verify_access_token(server_config)("token")


def test_invalid_token_no_access(
    server_config: OIDCConfig,
    mock_authn_server: responses.RequestsMock,
):
    with pytest.raises(HTTPException) as exec, mock_authn_server:
        main.verify_access_token(server_config)("bad_token")
    assert exec.value.status_code == HTTPStatus.UNAUTHORIZED


def test_expired_token_no_access(
    server_config: OIDCConfig,
    mock_authn_server: responses.RequestsMock,
):
    with pytest.raises(HTTPException) as exec, mock_authn_server:
        main.verify_access_token(server_config)("expired_token")
    assert exec.value.status_code == HTTPStatus.UNAUTHORIZED

import base64
import os
from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import jwt
import pytest
import responses
from fastapi.exceptions import HTTPException
from starlette.status import HTTP_403_FORBIDDEN

from blueapi.config import CLIClientConfig, OAuthClientConfig, OAuthServerConfig
from blueapi.service import main
from blueapi.service.authentication import Authenticator, SessionManager


@pytest.fixture
def authn_server_url() -> str:
    return "https://auth.example.com/realms/sample/.well-known/openid-configuration"


@pytest.fixture
def authn_server(authn_server_url: str):
    mock = responses.RequestsMock()
    mock.get(
        url=authn_server_url,
        content_type="application/json",
        json={
            "device_authorization_endpoint": "https://example.com/device_authorization",
            "authorization_endpoint": "https://example.com/authorization",
            "token_endpoint": "https://example.com/token",
            "issuer": "https://example.com",
            "jwks_uri": "https://example.com/.well-known/jwks.json",
            "end_session_endpoint": "https://example.com/logout",
            "id_token_signing_alg_values_supported": ["RS256", "RS384", "RS512"],
        },
    )

    return mock


@pytest.fixture
def configure_refreshed_token(authn_server: responses.RequestsMock):
    authn_server.post(
        url="https://example.com/token",
        json={"access_token": "new_access_token"},
    )

    return authn_server


@pytest.fixture
def configure_device_flow_token(authn_server: responses.RequestsMock):
    authn_server.post(
        url="https://example.com/device_authorization",
        json={"expires_in": 30, "interval": 5, "device_code": "device_code"},
    )
    authn_server.post(
        url="https://example.com/token",
        json={"access_token": "access_token"},
    )

    return authn_server


@pytest.fixture
def configure_awaiting_token(authn_server: responses.RequestsMock):
    authn_server.post(
        url="https://example.com/token",
        json={"error": "authorization_pending"},
        status=HTTP_403_FORBIDDEN,
    )

    return authn_server


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
def server_config(authn_server_url: str, authn_server) -> OAuthServerConfig:
    return OAuthServerConfig(oidc_config_url=authn_server_url)


@pytest.fixture
def session_manager(
    client_config: OAuthClientConfig, server_config: OAuthServerConfig
) -> SessionManager | None:
    return SessionManager.from_config(server_config, client_config)


@pytest.fixture
def connected_client_config(client_config: OAuthClientConfig):
    assert isinstance(client_config, CLIClientConfig)
    with open(client_config.token_file_path, "w") as token_file:
        # base64 encoded token
        token_file.write(
            base64.b64encode(
                b'{"access_token":"token","refresh_token":"refresh_token"}'
            ).decode("utf-8")
        )
    return client_config


@pytest.fixture
def authenticator(
    server_config: OAuthServerConfig, client_config: OAuthClientConfig
) -> Authenticator:
    return Authenticator(server_config, client_config)


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
    authn_server: responses.RequestsMock,
    session_manager: SessionManager,
):
    authn_server.post(
        url="https://example.com/token",
        json={"access_token": "access_token"},
    )
    with authn_server:
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


def test_valid_token_access_granted(mock_decode_jwt, authenticator: Authenticator):
    with (
        patch.object(main, "AUTHENTICATOR", authenticator),
        patch("blueapi.service.Authenticator.decode_jwt", mock_decode_jwt),
    ):
        decode_return_value = {"token": "valid_token", "name": "John Doe"}
        mock_decode_jwt.return_value = decode_return_value
        main.verify_access_token("token")


def test_invalid_token_no_access(mock_decode_jwt, authenticator: Authenticator):
    with pytest.raises(HTTPException) as exec:
        with (
            patch.object(main, "AUTHENTICATOR", authenticator),
            patch("blueapi.service.Authenticator.decode_jwt", mock_decode_jwt),
        ):
            main.verify_access_token("bad_token")
    assert exec.value.status_code == HTTPStatus.UNAUTHORIZED


def test_expired_token_no_access(mock_decode_jwt, authenticator: Authenticator):
    with pytest.raises(HTTPException) as exec:
        with (
            patch.object(main, "AUTHENTICATOR", authenticator),
            patch("blueapi.service.Authenticator.decode_jwt", mock_decode_jwt),
        ):
            main.verify_access_token("expired_token")
    assert exec.value.status_code == HTTPStatus.UNAUTHORIZED


@pytest.fixture
def mock_decode_jwt():
    def mock_decode(token: str) -> dict[str, Any] | None:
        if token == "expired_token":
            raise jwt.ExpiredSignatureError
        if token == "token":
            return {
                "name": "John Doe",
                "fedid": "jd1",
            }
        return None

    return Mock(side_effect=mock_decode)

import base64
import os
from http import HTTPStatus
from pathlib import Path
from unittest import mock

import jwt
import pytest
import requests
from fastapi.exceptions import HTTPException
from jwt import PyJWTError

from blueapi.config import CLIClientConfig, OAuthClientConfig, OAuthServerConfig
from blueapi.service import main
from blueapi.service.authentication import Authenticator, SessionManager


@pytest.fixture
def mock_client_config(tmp_path: Path) -> OAuthClientConfig:
    return CLIClientConfig(
        client_id="client_id",
        client_audience="client_audience",
        token_file_path=tmp_path / "token",
    )


@pytest.fixture
@mock.patch("requests.get")
def mock_server_config(mock_requests_get) -> OAuthServerConfig:
    mock_requests_get.return_value.status_code = 200
    mock_requests_get.return_value.json.return_value = {
        "device_authorization_endpoint": "https://example.com/device_authorization",
        "authorization_endpoint": "https://example.com/authorization",
        "token_endpoint": "https://example.com/token",
        "issuer": "https://example.com",
        "jwks_uri": "https://example.com/.well-known/jwks.json",
        "end_session_endpoint": "https://example.com/logout",
    }
    return OAuthServerConfig(
        oidc_config_url="https://auth.example.com/realms/sample/.well-known/openid-configuration",
    )


@pytest.fixture
def mock_session_manager(
    mock_client_config: OAuthClientConfig, mock_server_config: OAuthServerConfig
) -> SessionManager | None:
    return SessionManager.from_config(mock_server_config, mock_client_config)


@pytest.fixture
def mock_connected_client_config(mock_client_config: OAuthClientConfig):
    assert isinstance(mock_client_config, CLIClientConfig)
    with open(mock_client_config.token_file_path, "w") as token_file:
        # base64 encoded token
        token_file.write(
            base64.b64encode(
                b'{"access_token":"token","refresh_token":"refresh_token"}'
            ).decode("utf-8")
        )
    return mock_client_config


@pytest.fixture
def mock_authenticator(
    mock_server_config: OAuthServerConfig, mock_client_config: OAuthClientConfig
) -> Authenticator:
    return Authenticator(mock_server_config, mock_client_config)


@mock.patch("jwt.decode")
@mock.patch("jwt.PyJWKClient.get_signing_key_from_jwt")
def test_verify_token_valid(
    mock_get_signing_key, mock_decode, mock_authenticator: Authenticator
):
    decode_retun_value = {"token": "valid_token", "name": "John Doe"}
    mock_decode.return_value = decode_retun_value
    valid_token = mock_authenticator.verify_token(decode_retun_value["token"])
    assert valid_token


@mock.patch("jwt.decode")
@mock.patch("jwt.PyJWKClient.get_signing_key_from_jwt")
def test_verify_token_invalid(
    mock_get_signing_key, mock_decode, mock_authenticator: Authenticator
):
    mock_decode.side_effect = jwt.ExpiredSignatureError
    token = "invalid_token"
    with pytest.raises(PyJWTError):
        mock_authenticator.verify_token(token)


@mock.patch("jwt.decode")
@mock.patch("jwt.PyJWKClient.get_signing_key_from_jwt")
def test_user_info(
    mock_get_signing_key,
    mock_decode,
    mock_authenticator: Authenticator,
):
    mock_decode.return_value = {
        "name": "John Doe",
        "fedid": "12345",
    }
    mock_authenticator.print_user_info("valid_token")


def test_logout(
    mock_session_manager: SessionManager, mock_connected_client_config: CLIClientConfig
):
    assert os.path.exists(mock_connected_client_config.token_file_path)  # type: ignore
    mock_session_manager.logout()
    assert not os.path.exists(mock_connected_client_config.token_file_path)  # type: ignore


@mock.patch("requests.post")
def test_refresh_auth_token(
    mock_post,
    mock_session_manager: SessionManager,
    mock_connected_client_config: OAuthClientConfig,
):
    mock_post.return_value.status_code = HTTPStatus.OK
    mock_post.return_value.json.return_value = {"access_token": "new_access_token"}
    result = mock_session_manager.refresh_auth_token()
    assert result == {"access_token": "new_access_token"}


@mock.patch("requests.post")
def test_get_device_code(
    mock_post,
    mock_session_manager: SessionManager,
):
    mock_post.return_value.status_code = HTTPStatus.OK
    mock_post.return_value.json.return_value = {"device_code": "device_code"}
    device_code = mock_session_manager.get_device_code()
    assert device_code == "device_code"


@mock.patch("requests.post")
def test_failed_device_code_get(
    mock_post,
    mock_session_manager: SessionManager,
):
    mock_post.return_value.status_code = HTTPStatus.BAD_REQUEST
    mock_post.return_value.json.return_value = {"details": "Not Found"}
    with pytest.raises(
        requests.exceptions.RequestException, match="Failed to get device code."
    ):
        mock_session_manager.get_device_code()


@mock.patch("requests.post")
def test_poll_for_token(
    mock_post,
    mock_session_manager: SessionManager,
):
    mock_post.return_value.status_code = HTTPStatus.OK
    mock_post.return_value.json.return_value = {"access_token": "access_token"}
    device_code = "device_code"
    token = mock_session_manager.poll_for_token(device_code)
    assert token == {"access_token": "access_token"}


@mock.patch("requests.post")
@mock.patch("time.sleep")
def test_poll_for_token_timeout(
    mock_sleep,
    mock_post,
    mock_session_manager: SessionManager,
):
    mock_post.return_value.status_code = HTTPStatus.BAD_REQUEST
    device_code = "device_code"
    with pytest.raises(TimeoutError):
        mock_session_manager.poll_for_token(
            device_code, timeout=1, polling_interval=0.1
        )


def test_valid_token_access_granted(mock_authenticator):
    with mock.patch.object(main, "AUTHENTICATOR", mock_authenticator):
        mock_authenticator.verify_token = True
        main.verify_access_token("token")


def test_invalid_token_no_access(mock_authenticator):
    with pytest.raises(HTTPException) as exec:
        with mock.patch.object(main, "AUTHENTICATOR", mock_authenticator):
            mock_authenticator.verify_token = False
            main.verify_access_token("token")
        assert exec.value.status_code == HTTPStatus.UNAUTHORIZED


def test_verify_access_token_failure(mock_authenticator):
    with pytest.raises(HTTPException) as exec:
        with mock.patch.object(main, "AUTHENTICATOR", mock_authenticator):
            main.verify_access_token("token")
        assert exec.value.status_code == HTTPStatus.UNAUTHORIZED

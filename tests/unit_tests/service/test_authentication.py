import os
from http import HTTPStatus
from unittest import TestCase, mock

import jwt
import pytest
from jwt import PyJWTError

from blueapi.config import BaseAuthConfig, CLIAuthConfig, OauthConfig
from blueapi.service.authentication import Authenticator, TokenManager


class TestAuthenticator(TestCase):
    @mock.patch("requests.get")
    def setUp(self, mock_requests_get):
        mock_requests_get.return_value.status_code = 200
        mock_requests_get.return_value.json.return_value = {
            "device_authorization_endpoint": "https://example.com/device_authorization",
            "authorization_endpoint": "https://example.com/authorization",
            "token_endpoint": "https://example.com/token",
            "issuer": "https://example.com",
            "jwks_uri": "https://example.com/.well-known/jwks.json",
            "end_session_endpoint": "https://example.com/logout",
        }
        self.oauth_config = OauthConfig(
            oidc_config_url="https://auth.example.com/realms/sample/.well-known/openid-configuration",
        )
        self.base_auth_config = BaseAuthConfig(
            client_id="example_client_id", client_audience="example_audience"
        )
        self.authenticator = Authenticator(self.oauth_config, self.base_auth_config)

    @mock.patch("jwt.decode")
    @mock.patch("jwt.PyJWKClient.get_signing_key_from_jwt")
    def test_verify_token_valid(self, mock_get_signing_key, mock_decode):
        decode_retun_value = {"token": "valid_token", "name": "John Doe"}
        mock_decode.return_value = decode_retun_value
        valid_token = self.authenticator.verify_token(decode_retun_value["token"])
        self.assertTrue(valid_token)

    @mock.patch("jwt.decode")
    @mock.patch("jwt.PyJWKClient.get_signing_key_from_jwt")
    def test_verify_token_invalid(self, mock_get_signing_key, mock_decode):
        mock_decode.side_effect = jwt.ExpiredSignatureError
        token = "invalid_token"
        with pytest.raises(PyJWTError):
            self.authenticator.verify_token(token)

    @mock.patch("jwt.decode")
    @mock.patch("jwt.PyJWKClient.get_signing_key_from_jwt")
    def test_user_info(
        self,
        mock_get_signing_key,
        mock_decode,
    ):
        mock_decode.return_value = {
            "name": "John Doe",
            "fedid": "12345",
        }
        self.authenticator.print_user_info("valid_token")


class TestTokenManager(TestCase):
    @mock.patch("requests.get")
    def setUp(self, mock_requests_get):
        mock_requests_get.return_value.status_code = 200
        mock_requests_get.return_value.json.return_value = {
            "device_authorization_endpoint": "https://example.com/device_authorization",
            "authorization_endpoint": "https://example.com/authorization",
            "token_endpoint": "https://example.com/token",
            "issuer": "https://example.com",
            "jwks_uri": "https://example.com/.well-known/jwks.json",
            "end_session_endpoint": "https://example.com/logout",
        }
        self.oauth_config = OauthConfig(
            oidc_config_url="https://auth.example.com/realms/sample/.well-known/openid-configuration",
        )
        self.cli_auth_config = CLIAuthConfig(
            client_id="client_id",
            client_audience="client_audience",
            token_file_path="~/token",
        )
        self.token_manager = TokenManager(self.oauth_config, self.cli_auth_config)

    @mock.patch("os.path.exists")
    @mock.patch("os.remove")
    def test_logout(self, mock_remove, mock_exists):
        mock_exists.return_value = True
        self.token_manager.logout()
        mock_remove.assert_called_once_with(
            os.path.expanduser(self.cli_auth_config.token_file_path)
        )

    @mock.patch("requests.post")
    def test_refresh_auth_token(self, mock_post):
        self.token_manager.token = {"refresh_token": "refresh_token"}
        mock_post.return_value.status_code = HTTPStatus.OK
        mock_post.return_value.json.return_value = {"access_token": "new_access_token"}
        result = self.token_manager.refresh_auth_token()
        self.assertTrue(result)

    @mock.patch("requests.post")
    def test_get_device_code(self, mock_post):
        mock_post.return_value.status_code = HTTPStatus.OK
        mock_post.return_value.json.return_value = {"device_code": "device_code"}
        device_code = self.token_manager.get_device_code()
        self.assertEqual(device_code, "device_code")

    @mock.patch("requests.post")
    def test_poll_for_token(self, mock_post):
        mock_post.return_value.status_code = HTTPStatus.OK
        mock_post.return_value.json.return_value = {"access_token": "access_token"}
        device_code = "device_code"
        token = self.token_manager.poll_for_token(device_code)
        self.assertEqual(token, {"access_token": "access_token"})

    @mock.patch("requests.post")
    @mock.patch("time.sleep")
    def test_poll_for_token_timeout(self, mock_sleep, mock_post):
        mock_post.return_value.status_code = HTTPStatus.BAD_REQUEST
        device_code = "device_code"
        with self.assertRaises(TimeoutError):
            self.token_manager.poll_for_token(
                device_code, timeout=1, polling_interval=0.1
            )

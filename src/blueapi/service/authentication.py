from __future__ import annotations

import base64
import json
import os
import time
from abc import ABC, abstractmethod
from enum import Enum
from http import HTTPStatus
from pathlib import Path
from typing import Any, cast

import jwt
import requests

from blueapi.config import (
    CLIClientConfig,
    OAuthClientConfig,
    OAuthServerConfig,
)


class AuthenticationType(Enum):
    DEVICE = "device"
    PKCE = "pkce"


class Authenticator:
    def __init__(self, server_config: OAuthServerConfig):
        self._server_config: OAuthServerConfig = server_config

    def decode_jwt(self, token: str) -> dict[str, str]:
        signing_key = jwt.PyJWKClient(
            self._server_config.jwks_uri
        ).get_signing_key_from_jwt(token)
        decode: dict[str, str] = jwt.decode(
            token,
            signing_key.key,
            algorithms=self._server_config.signing_algos,
            verify=True,
            audience=self._server_config.audience,
            issuer=self._server_config.issuer,
        )
        return decode

    def print_user_info(self, token: str) -> None:
        decode: dict[str, str] = self.decode_jwt(token)
        print(f'Logged in as {decode.get("name")} with fed-id {decode.get("fedid")}')


class TokenManager(ABC):
    @abstractmethod
    def save_token(self, token: dict[str, Any]) -> None: ...
    @abstractmethod
    def load_token(token) -> dict[str, Any] | None: ...
    @abstractmethod
    def delete_token(self): ...


class CliTokenManager(TokenManager):
    def __init__(self, token_file_path: Path) -> None:
        self._token_file_path: Path = token_file_path

    def _file_path(self) -> str:
        return os.path.expanduser(self._token_file_path)

    def save_token(self, token: dict[str, Any]) -> None:
        token_json: str = json.dumps(token)
        token_bytes: bytes = token_json.encode("utf-8")
        token_base64: bytes = base64.b64encode(token_bytes)
        with open(self._file_path(), "wb") as token_file:
            token_file.write(token_base64)

    def load_token(self) -> dict[str, Any] | None:
        file_path = self._file_path()
        if not os.path.exists(file_path):
            return None
        with open(file_path, "rb") as token_file:
            token_base64: bytes = token_file.read()
            token_bytes: bytes = base64.b64decode(token_base64)
            token_json: str = token_bytes.decode("utf-8")
            return json.loads(token_json)

    def delete_token(self) -> None:
        Path(self._file_path()).unlink(missing_ok=True)


class SessionManager:
    def __init__(
        self,
        server_config: OAuthServerConfig,
        client_config: OAuthClientConfig,
        token_manager: TokenManager,
    ) -> None:
        self._server_config: OAuthServerConfig = server_config
        self._client_config: OAuthClientConfig = client_config
        self.authenticator: Authenticator = Authenticator(server_config, client_config)
        self._token_manager = token_manager

    @classmethod
    def from_config(
        cls,
        server_config: OAuthServerConfig | None,
        client_config: OAuthClientConfig | None,
    ) -> SessionManager | None:
        if server_config and client_config:
            if isinstance(client_config, CLIClientConfig):
                return SessionManager(
                    server_config,
                    client_config,
                    CliTokenManager(Path(client_config.token_file_path)),
                )
        return None

    def get_token(self) -> dict[str, Any] | None:
        return self._token_manager.load_token()

    def logout(self) -> None:
        self._token_manager.delete_token()

    def refresh_auth_token(self) -> dict[str, Any] | None:
        if token := self._token_manager.load_token():
            response = requests.post(
                self._server_config.token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "client_id": self._client_config.client_id,
                    "grant_type": "refresh_token",
                    "refresh_token": token["refresh_token"],
                },
            )
            if response.status_code == HTTPStatus.OK:
                token = response.json()
                if token:
                    self._token_manager.save_token(token)
                    return token
        return None

    def poll_for_token(
        self, device_code: str, polling_interval: float, expires_in: float
    ) -> dict[str, Any]:
        expiry_time: float = time.time() + expires_in
        while time.time() < expiry_time:
            response = requests.post(
                self._server_config.token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                    "client_id": self._client_config.client_id,
                },
            )
            if response.status_code == HTTPStatus.OK:
                return response.json()
            time.sleep(polling_interval)

        raise TimeoutError("Polling timed out")

    def start_device_flow(self) -> None:
        if token := self._token_manager.load_token():
            try:
                access_token_info: dict[str, Any] = self.authenticator.decode_jwt(
                    token["access_token"]
                )
                if access_token_info:
                    self.authenticator.print_user_info(token["access_token"])
                    return
            except jwt.ExpiredSignatureError:
                if token := self.refresh_auth_token():
                    self.authenticator.print_user_info(token["access_token"])
                    return

        response: requests.Response = requests.post(
            self._server_config.device_auth_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_id": self._client_config.client_id,
                "scope": "openid profile offline_access",
                "audience": self._client_config.client_audience,
            },
        )

        if response.status_code == HTTPStatus.OK:
            response_json: dict[str, Any] = response.json()
            device_code = cast(str, response_json.get("device_code"))
            interval = cast(float, response_json.get("interval"))
            expires_in = cast(float, response_json.get("expires_in"))
            print(
                "Please login from this URL:- "
                f"{response_json['verification_uri_complete']}"
            )
            auth_token_json: dict[str, Any] = self.poll_for_token(
                device_code, interval, expires_in
            )
            decoded_token: dict[str, Any] = self.authenticator.decode_jwt(
                auth_token_json["access_token"]
            )
            if decoded_token:
                self._token_manager.save_token(auth_token_json)
                self.authenticator.print_user_info(auth_token_json["access_token"])
        else:
            print("Failed to login")

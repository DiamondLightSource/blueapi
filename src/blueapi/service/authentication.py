from __future__ import annotations

import base64
import json
import os
import time
from abc import ABC, abstractmethod
from collections.abc import Iterable
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


class Authenticator:
    def __init__(self, server_config: OAuthServerConfig):
        self._server_config: OAuthServerConfig = server_config

    def decode_jwt(
        self, token: str, audience: str | Iterable[str] | None = None
    ) -> dict[str, str]:
        signing_key = jwt.PyJWKClient(
            self._server_config.jwks_uri
        ).get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=self._server_config.signing_algos,
            verify=True,
            audience=audience,
            issuer=self._server_config.issuer,
        )


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
        token_base64: bytes = base64.b64encode(token_json.encode("utf-8"))
        with open(self._file_path(), "wb") as token_file:
            token_file.write(token_base64)

    def load_token(self) -> dict[str, Any] | None:
        file_path = self._file_path()
        if not os.path.exists(file_path):
            return None
        with open(file_path, "rb") as token_file:
            token_base64: bytes = token_file.read()
            token_json: bytes = base64.b64decode(token_base64).decode("utf-8")
            return json.loads(token_json)

    def delete_token(self) -> None:
        Path(self._file_path()).unlink(missing_ok=True)


class SessionManager:
    def __init__(
        self,
        server_config: OAuthServerConfig,
        client_config: OAuthClientConfig,
    ) -> None:
        self._server_config = server_config
        self._client_id = client_config.client_id
        self._client_audience = client_config.client_audience
        self.authenticator: Authenticator = Authenticator(server_config)
        self._token_manager: TokenManager | None = (
            CliTokenManager(client_config.token_file_path)
            if isinstance(client_config, CLIClientConfig)
            else None
        )

    def get_token(self) -> dict[str, Any] | None:
        if self._token_manager:
            return self._token_manager.load_token()
        return None

    def logout(self) -> None:
        if self._token_manager:
            self._token_manager.delete_token()

    def refresh_auth_token(self) -> dict[str, Any] | None:
        if not self._token_manager:
            print("Session not configured to persist, no token to refresh")
            return None
        token = self._token_manager.load_token()
        if not token:
            print("No current Session, no token to refresh")
            return None
        response = requests.post(
            self._server_config.token_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_id": self._client_id,
                "grant_type": "refresh_token",
                "refresh_token": token["refresh_token"],
            },
        )
        if response.status_code == HTTPStatus.OK and (token := response.json()):
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
                    "client_id": self._client_id,
                },
            )
            if response.status_code == HTTPStatus.OK:
                return response.json()
            time.sleep(polling_interval)

        raise TimeoutError("Polling timed out")

    def start_device_flow(self) -> None:
        if not self._token_manager:
            print("Session not configured to persist, no token to refresh")
            return None

        if token := self._token_manager.load_token():
            try:
                self.authenticator.decode_jwt(
                    token["access_token"], self._client_audience
                )
                print("Cached token still valid, skipping flow")
                return
            except jwt.ExpiredSignatureError:
                if token := self.refresh_auth_token():
                    print("Refreshed cached token, skipping flow")
                    return
            except Exception:
                print("Problem with cached token, starting new session")
                self._token_manager.delete_token()

        response: requests.Response = requests.post(
            self._server_config.device_auth_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_id": self._client_id,
                "scope": "openid profile offline_access",
                "audience": self._client_audience,
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
                auth_token_json["access_token"], self._client_audience
            )
            if decoded_token:
                if self._token_manager:
                    self._token_manager.save_token(auth_token_json)
                    print("Logged in and cached new token")
                else:
                    print("Logged in but not configured to persist session")

        else:
            print("Failed to login")

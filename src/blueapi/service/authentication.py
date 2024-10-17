import base64
import json
import os
import time
from abc import ABC, abstractmethod
from enum import Enum
from http import HTTPStatus
from pathlib import Path
from typing import Any

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
    def __init__(
        self,
        server_config: OAuthServerConfig,
        client_config: OAuthClientConfig,
    ):
        self._server_config: OAuthServerConfig = server_config
        self._client_config: OAuthClientConfig = client_config

    def verify_token(self, token: str, verify_expiration: bool = True) -> bool:
        self.decode_jwt(token, verify_expiration)
        return True

    def decode_jwt(self, token: str, verify_expiration: bool = True) -> dict[str, str]:
        signing_key = jwt.PyJWKClient(
            self._server_config.jwks_uri
        ).get_signing_key_from_jwt(token)
        decode: dict[str, str] = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_exp": verify_expiration},
            verify=True,
            audience=self._client_config.client_audience,
            issuer=self._server_config.issuer,
            leeway=5,
        )
        return decode

    def print_user_info(self, token: str) -> None:
        decode: dict[str, str] = self.decode_jwt(token)
        print(f'Logged in as {decode.get("name")} with fed-id {decode.get("fedid")}')


class TokenManager(ABC):
    @abstractmethod
    def save_token(self, token: dict[str, Any]): ...
    @abstractmethod
    def load_token(token) -> dict[str, Any] | None: ...
    @abstractmethod
    def delete_token(self): ...


class CLITokenManager(TokenManager):
    def __init__(self, token_file_path: Path) -> None:
        self._token_file_path: Path = token_file_path

    def save_token(self, token: dict[str, Any]) -> None:
        token_json: str = json.dumps(token)
        token_bytes: bytes = token_json.encode("utf-8")
        token_base64: bytes = base64.b64encode(token_bytes)
        with open(os.path.expanduser(self._token_file_path), "wb") as token_file:
            token_file.write(token_base64)

    def load_token(self) -> dict[str, Any] | None:
        file_path = os.path.expanduser(self._token_file_path)
        if not os.path.exists(file_path):
            return None
        with open(file_path, "rb") as token_file:
            token_base64: bytes = token_file.read()
            token_bytes: bytes = base64.b64decode(token_base64)
            token_json: str = token_bytes.decode("utf-8")
            return json.loads(token_json)

    def delete_token(self) -> None:
        if os.path.exists(os.path.expanduser(self._token_file_path)):
            os.remove(os.path.expanduser(self._token_file_path))


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
    ) -> "SessionManager":
        if server_config and client_config:
            if isinstance(client_config, CLIClientConfig):
                return SessionManager(
                    server_config,
                    client_config,
                    CLITokenManager(Path(client_config.token_file_path)),  # type: ignore
                )
        # raise NotImplementedError("Only CLI client config is supported")

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
                self._token_manager.save_token(token)
                return token

    def get_device_code(self):
        response: requests.Response = requests.post(
            self._server_config.token_url,
            data={
                "client_id": self._client_config.client_id,
                "scope": "openid profile offline_access",
                "audience": self._client_config.client_audience,
            },
        )
        response_data: dict[str, str] = response.json()
        if response.status_code == 200:
            return response_data["device_code"]
        raise Exception("Failed to get device code.")

    def poll_for_token(
        self, device_code: str, timeout: float = 30, polling_interval: float = 0.5
    ) -> dict[str, Any]:
        too_late: float = time.time() + timeout
        while time.time() < too_late:
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
            if response.status_code == HTTPStatus.BAD_REQUEST:
                polling_interval += 0.5
            time.sleep(polling_interval)

        raise TimeoutError("Polling timed out")

    def start_device_flow(self) -> None:
        if token := self._token_manager.load_token():
            try:
                is_token_vaild: bool = self.authenticator.verify_token(
                    token["access_token"]
                )
                if is_token_vaild:
                    self.authenticator.print_user_info(token["access_token"])
                    return
            except jwt.ExpiredSignatureError:
                if token := self.refresh_auth_token():
                    self.authenticator.print_user_info(token["access_token"])
                    return

        response: requests.Response = requests.post(
            self._server_config.device_auth_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"client_id": self._client_config.client_id},
        )

        if response.status_code == HTTPStatus.OK:
            response_json: Any = response.json()
            device_code: str = response_json.get("device_code")
            print(
                "Please login from this URL:- "
                f"{response_json['verification_uri_complete']}"
            )
            auth_token_json: dict[str, Any] = self.poll_for_token(device_code)
            valid_token: bool = self.authenticator.verify_token(
                auth_token_json["access_token"]
            )
            if valid_token:
                self._token_manager.save_token(auth_token_json)
                self.authenticator.print_user_info(auth_token_json["access_token"])

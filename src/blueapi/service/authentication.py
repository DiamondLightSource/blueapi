from __future__ import annotations

import base64
import os
import threading
import time
import webbrowser
from abc import ABC, abstractmethod
from enum import Enum
from functools import cached_property
from http import HTTPStatus
from pathlib import Path
from typing import Any, cast

import httpx
import jwt
import requests
from pydantic import BaseModel, TypeAdapter, computed_field
from requests.auth import AuthBase

from blueapi.config import OIDCConfig, TiledConfig
from blueapi.service.model import Cache

DEFAULT_CACHE_DIR = "~/.cache/"
SCOPES = "openid"


class CacheManager(ABC):
    @abstractmethod
    def can_access_cache(self) -> bool: ...
    @abstractmethod
    def save_cache(self, cache: Cache) -> None: ...
    @abstractmethod
    def load_cache(self) -> Cache: ...
    @abstractmethod
    def delete_cache(self) -> None: ...


class SessionCacheManager(CacheManager):
    def __init__(self, token_path: Path | None) -> None:
        self._token_path: Path = (
            token_path if token_path else self._default_token_cache_path()
        )

    @cached_property
    def _file_path(self) -> str:
        return os.path.expanduser(self._token_path)

    def save_cache(self, cache: Cache) -> None:
        self.delete_cache()
        with open(self._file_path, "xb") as token_file:
            token_file.write(base64.b64encode(cache.model_dump_json().encode("utf-8")))
        os.chmod(self._file_path, 0o600)

    def load_cache(self) -> Cache:
        with open(self._file_path, "rb") as cache_file:
            return TypeAdapter(Cache).validate_json(
                base64.b64decode(cache_file.read()).decode("utf-8")
            )

    def delete_cache(self) -> None:
        Path(self._file_path).unlink(missing_ok=True)

    @staticmethod
    def _default_token_cache_path() -> Path:
        """
        Return the default cache file path.
        """
        cache_path = os.environ.get("XDG_CACHE_HOME", DEFAULT_CACHE_DIR)
        return Path(cache_path).expanduser() / "blueapi_cache"

    def can_access_cache(self) -> bool:
        assert self._token_path
        try:
            self._token_path.write_text("")
        except IsADirectoryError:
            print("Invalid path: a directory path was provided instead of a file path")
            return False
        except PermissionError:
            print(f"Permission denied: Cannot write to {self._token_path.absolute()}")
            return False
        return True


class SessionManager:
    def __init__(self, server_config: OIDCConfig, cache_manager: CacheManager) -> None:
        self._server_config = server_config
        self._cache_manager: CacheManager = cache_manager

    @classmethod
    def from_cache(cls, auth_token_path: Path | None) -> SessionManager:
        cache_manager = SessionCacheManager(auth_token_path)
        cache = cache_manager.load_cache()
        return SessionManager(
            server_config=cache.oidc_config, cache_manager=cache_manager
        )

    def delete_cache(self) -> None:
        self._cache_manager.delete_cache()

    def get_valid_access_token(self) -> str:
        """
        Retrieves a valid access token.

        Returns:
            str: A valid access token if successful.
            "": If the operation fails (no valid token could be fetched or refreshed)
        """
        try:
            cache = self._cache_manager.load_cache()
            self.decode_jwt(cache.access_token)
            return cache.access_token
        except jwt.ExpiredSignatureError:
            cache = self._cache_manager.load_cache()
            return self._refresh_auth_token(cache.refresh_token)
        except Exception:
            self.delete_cache()
            return ""

    @cached_property
    def client(self):
        return jwt.PyJWKClient(self._server_config.jwks_uri)

    def decode_jwt(self, json_web_token: str):
        signing_key = self.client.get_signing_key_from_jwt(json_web_token)
        return jwt.decode(
            json_web_token,
            signing_key.key,
            algorithms=self._server_config.id_token_signing_alg_values_supported,
            verify=True,
            audience=self._server_config.client_audience,
            issuer=self._server_config.issuer,
        )

    def logout(self) -> None:
        cache = self._cache_manager.load_cache()
        self.delete_cache()
        try:
            response = requests.get(
                self._server_config.end_session_endpoint,
                params={
                    "id_token_hint": cache.id_token,
                    "client_id": self._server_config.client_id,
                },
            )
            response.raise_for_status()
            print("Logged out")
        except Exception as e:
            print(
                "An unexpected error occurred while attempting "
                f"to log out from the server.{e}"
            )

    def _refresh_auth_token(self, refresh_token: str) -> str:
        response = requests.post(
            self._server_config.token_endpoint,
            data={
                "client_id": self._server_config.client_id,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code == HTTPStatus.OK:
            token = response.json()
            self._cache_manager.save_cache(
                Cache(
                    oidc_config=self._server_config,
                    refresh_token=token["refresh_token"],
                    id_token=token["id_token"],
                    access_token=token["access_token"],
                ),
            )
            return token["access_token"]
        else:
            self.delete_cache()
            return ""

    def poll_for_token(
        self, device_code: str, polling_interval: float, expires_in: float
    ) -> dict[str, Any]:
        expiry_time: float = time.time() + expires_in
        while time.time() < expiry_time:
            response = requests.post(
                self._server_config.token_endpoint,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                    "client_id": self._server_config.client_id,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if response.status_code == HTTPStatus.OK:
                return response.json()
            time.sleep(polling_interval)

        raise TimeoutError("Polling timed out")

    def start_device_flow(self):
        assert self._cache_manager.can_access_cache()
        print("Logging in")
        response: requests.Response = requests.post(
            self._server_config.device_authorization_endpoint,
            data={
                "client_id": self._server_config.client_id,
                "scope": SCOPES,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        response.raise_for_status()

        response_json: dict[str, Any] = response.json()
        device_code = cast(str, response_json.get("device_code"))
        interval = cast(float, response_json.get("interval"))
        expires_in = cast(float, response_json.get("expires_in"))
        webbrowser.open_new_tab(response_json["verification_uri_complete"])
        print(
            f"Please login from this URL:- {response_json['verification_uri_complete']}"
        )
        auth_token_json: dict[str, Any] = self.poll_for_token(
            device_code, interval, expires_in
        )
        self._cache_manager.save_cache(
            Cache(
                oidc_config=self._server_config,
                refresh_token=auth_token_json["refresh_token"],
                id_token=auth_token_json["id_token"],
                access_token=auth_token_json["access_token"],
            )
        )
        print("Logged in and cached new token")


class JWTAuth(AuthBase):
    def __init__(self, session_manager: SessionManager | None):
        self.token: str = (
            session_manager.get_valid_access_token() if session_manager else ""
        )

    def __call__(self, request):
        if self.token:
            request.headers["Authorization"] = f"Bearer {self.token}"
        return request


class TokenType(str, Enum):
    refresh_token = "refresh_token"
    access_token = "access_token"


class Token(BaseModel):
    token: str
    expires_at: float | None

    @computed_field
    @property
    def expired(self) -> bool:
        if self.expires_at is None:
            # Assume token is valid
            return False
        return time.time() > self.expires_at

    def _get_token_expires_at(
        self, token_dict: dict[str, Any], token_type: TokenType
    ) -> int | None:
        expires_at = None
        if token_type == TokenType.access_token:
            if "expires_in" in token_dict:
                expires_at = int(time.time()) + int(token_dict["expires_in"])
        elif token_type == TokenType.refresh_token:
            if "refresh_expires_in" in token_dict:
                expires_at = int(time.time()) + int(token_dict["refresh_expires_in"])
        return expires_at

    def __init__(self, token_dict: dict[str, Any], token_type: TokenType):
        token = token_dict.get(token_type)
        if token is None:
            raise ValueError(f"Not able to find {token_type} in response")
        super().__init__(
            token=token, expires_at=self._get_token_expires_at(token_dict, token_type)
        )

    def __str__(self) -> str:
        return str(self.token)


class TiledAuth(httpx.Auth):
    def __init__(self, tiled_config: TiledConfig, blueapi_jwt_token: str):
        self._tiled_config = tiled_config
        self._blueapi_jwt_token = blueapi_jwt_token
        self._sync_lock = threading.RLock()
        self._access_token: Token | None = None
        self._refresh_token: Token | None = None

    def exchange_access_token(self):
        client_secret = self._tiled_config.token_exchange_secret.get_secret_value()
        request_data = {
            "client_id": self._tiled_config.requester_client_id,
            "client_secret": client_secret,
            "subject_token": self._blueapi_jwt_token,
            "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "requested_token_type": "urn:ietf:params:oauth:token-type:refresh_token",
        }
        with self._sync_lock:
            response = requests.post(
                self._tiled_config.token_url,
                data=request_data,
            )
            response.raise_for_status()
            self.sync_tokens(response.json())

    def refresh_token(self):
        if self._refresh_token is None:
            raise Exception("Cannot refresh session as no refresh token available")
        with self._sync_lock:
            client_secret = self._tiled_config.token_exchange_secret.get_secret_value()
            response = requests.post(
                self._tiled_config.token_url,
                data={
                    "client_id": self._tiled_config.requester_client_id,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": str(self._refresh_token),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            self.sync_tokens(response.json())

    def sync_tokens(self, response):
        self._access_token = Token(response, TokenType.access_token)
        self._refresh_token = Token(response, TokenType.refresh_token)

    def sync_auth_flow(self, request):
        if self._access_token is not None and self._access_token.expired is not True:
            request.headers["Authorization"] = f"Bearer {self._access_token}"
            yield request
        elif self._access_token is None:
            self.exchange_access_token()
            request.headers["Authorization"] = f"Bearer {self._access_token}"
            yield request
        else:
            self.refresh_token()
            request.headers["Authorization"] = f"Bearer {self._access_token}"
            yield request

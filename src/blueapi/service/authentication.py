from __future__ import annotations

import base64
import os
import time
from abc import ABC, abstractmethod
from functools import cached_property
from http import HTTPStatus
from pathlib import Path
from typing import Any, cast

import jwt
import requests
from pydantic import TypeAdapter
from requests.auth import AuthBase

from blueapi.config import OIDCConfig
from blueapi.service.model import Cache

BLUEAPI_CACHE_LOCATION = "~/.cache/blueapi_cache"


class CacheManager(ABC):
    @abstractmethod
    def save_cache(self, cache: Cache) -> None: ...
    @abstractmethod
    def load_cache(cache) -> Cache | None: ...
    @abstractmethod
    def delete_cache(self) -> None: ...


class SessionCacheManager(CacheManager):
    def __init__(self, token_path: Path | None) -> None:
        self._token_path: Path = token_path if token_path else self.get_xdg_cache_dir()

    @cached_property
    def _file_path(self) -> str:
        return os.path.expanduser(self._token_path)

    def save_cache(self, cache: Cache) -> None:
        cache_json: str = cache.model_dump_json()
        cache_base64: bytes = base64.b64encode(cache_json.encode("utf-8"))
        self.delete_cache()
        with open(self._file_path, "xb") as token_file:
            token_file.write(cache_base64)
        os.chmod(self._file_path, 0o600)

    def load_cache(self) -> Cache | None:
        try:
            with open(self._file_path, "rb") as cache_file:
                cache_base64: bytes = cache_file.read()
                cache_json: str = base64.b64decode(cache_base64).decode("utf-8")
                return TypeAdapter(Cache).validate_json(cache_json)
        except Exception:
            return None

    def delete_cache(self) -> None:
        Path(self._file_path).unlink(missing_ok=True)

    def get_xdg_cache_dir(self) -> Path:
        """
        Return the XDG cache directory.
        """
        cache_dir = os.environ.get("XDG_CACHE_HOME")
        if not cache_dir:
            cache_dir = os.path.expanduser(BLUEAPI_CACHE_LOCATION)
            if cache_dir.startswith("~/"):  # Expansion failed.
                raise ValueError("Please specify auth_token_path")
        return Path(cache_dir)


class SessionManager:
    def __init__(self, server_config: OIDCConfig, cache_manager: CacheManager) -> None:
        self._server_config = server_config
        self._cache_manager: CacheManager = cache_manager

    @classmethod
    def from_cache(cls, auth_token_path: Path | None) -> SessionManager | None:
        cacheManager = SessionCacheManager(auth_token_path)
        cache = cacheManager.load_cache()
        if cache:
            return SessionManager(
                server_config=cache.oidc_config, cache_manager=cacheManager
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
        cache = self._cache_manager.load_cache()
        if cache:
            try:
                self.decode_jwt(cache.access_token)
                return cache.access_token
            except jwt.ExpiredSignatureError:
                return self._refresh_auth_token(cache.refresh_token)
            except Exception:
                return ""
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
        try:
            cache = self._cache_manager.load_cache()
            if cache:
                response = requests.get(
                    self._server_config.end_session_endpoint,
                    params={
                        "id_token_hint": cache.id_token,
                        "client_id": self._server_config.client_id,
                    },
                )
                response.raise_for_status()
        except FileNotFoundError:
            ...
        except Exception as e:
            print(e)
        finally:
            self.delete_cache()

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
        response: requests.Response = requests.post(
            self._server_config.device_authorization_endpoint,
            data={
                "client_id": self._server_config.client_id,
                "scope": "openid offline_access",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        response.raise_for_status()

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

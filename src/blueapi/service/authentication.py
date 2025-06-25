from __future__ import annotations

import time
import webbrowser
from functools import cached_property
from http import HTTPStatus
from pathlib import Path
from typing import Any, cast

import jwt
import requests
from requests.auth import AuthBase

from blueapi.config import OIDCConfig
from blueapi.service.model import Cache
from blueapi.utils.caching import DiskCache

DEFAULT_CACHE_DIR = "~/.cache/"
SCOPES = "openid offline_access"


_CACHE_KEY = "auth_token"


class SessionManager:
    def __init__(self, server_config: OIDCConfig, cache_manager: DiskCache) -> None:
        self._server_config = server_config
        self._cache_manager: DiskCache = cache_manager

    @classmethod
    def from_cache(cls, auth_token_path: Path | None) -> SessionManager:
        cache_manager = DiskCache(auth_token_path)
        cache = cache_manager.get(_CACHE_KEY, deserialize_type=Cache)
        if cache is not None:
            return SessionManager(
                server_config=cache.oidc_config, cache_manager=cache_manager
            )
        else:
            raise KeyError("Local cache not found")

    def delete_cache(self) -> None:
        self._cache_manager.clear(_CACHE_KEY)

    def load_cache(self) -> Cache:
        cache = self._cache_manager.get(_CACHE_KEY, deserialize_type=Cache)
        if cache is not None:
            return cache
        else:
            raise KeyError("Local cache not found")

    def save_cache(self, cache: Cache | None) -> None:
        self._cache_manager.set(_CACHE_KEY, cache)

    def get_valid_access_token(self) -> str:
        """
        Retrieves a valid access token.

        Returns:
            str: A valid access token if successful.
            "": If the operation fails (no valid token could be fetched or refreshed)
        """
        try:
            cache = self.load_cache()
            self.decode_jwt(cache.access_token)
            return cache.access_token
        except jwt.ExpiredSignatureError:
            cache = self.load_cache()
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
        cache = self.load_cache()
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
            self.save_cache(
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
        # Verify that we can write to the cache before doing the
        # expensive login operation
        self.save_cache(None)

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
        if not webbrowser.open_new_tab(response_json["verification_uri_complete"]):
            print(
                "Please login from this URL:- "
                f"{response_json['verification_uri_complete']}"
            )
        auth_token_json: dict[str, Any] = self.poll_for_token(
            device_code, interval, expires_in
        )
        self.save_cache(
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

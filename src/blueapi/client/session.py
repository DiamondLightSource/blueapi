from __future__ import annotations

import base64
import logging
import os
import tempfile
import time
import webbrowser
from abc import ABC, abstractmethod
from functools import cached_property
from http import HTTPStatus
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

import jwt
import requests
from pydantic import TypeAdapter
from requests.auth import AuthBase

from blueapi.config import OIDCConfig
from blueapi.service.model import Cache

LOGGER = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = "~/.cache/"
CACHE_FILE_PREFIX = "blueapi_cache"
SCOPES = "openid offline_access"
# Refresh access tokens that expire within this many seconds, so that they do
# not expire between being checked here and being validated by the server
REFRESH_MARGIN_SECONDS = 30
REQUEST_TIMEOUT_SECONDS = 10


class AuthenticationServerUnavailableError(Exception):
    """
    The OIDC provider could not be reached (or failed) while refreshing tokens.

    The cached login is kept, as the refresh token may still be valid once the
    provider is reachable again.
    """


def default_cache_path(server_url: str | None = None) -> Path:
    """
    Default token cache file, one per blueapi server so that logging in to one
    server does not replace (or get confused with) the login for another.

    e.g. ~/.cache/blueapi_cache.i22-blueapi.diamond.ac.uk
         ~/.cache/blueapi_cache.localhost_8000
    """
    cache_dir = Path(os.environ.get("XDG_CACHE_HOME", DEFAULT_CACHE_DIR)).expanduser()
    if not server_url:
        return cache_dir / CACHE_FILE_PREFIX
    url = urlsplit(str(server_url))
    name = url.hostname or "default"
    if url.port is not None:
        name += f"_{url.port}"
    return cache_dir / f"{CACHE_FILE_PREFIX}.{name}"


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
    def __init__(self, token_path: Path | None, server_url: str | None = None) -> None:
        self._token_path: Path = (
            Path(token_path) if token_path else default_cache_path(server_url)
        )

    @cached_property
    def _file_path(self) -> str:
        return os.path.expanduser(self._token_path)

    def save_cache(self, cache: Cache) -> None:
        """
        Write the cache atomically so that another process reading it never
        sees a partially written (or missing) file.
        """
        self._create_parent_folder_if_necessary()
        directory = os.path.dirname(self._file_path)
        # mkstemp creates the file with 0o600 permissions
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".blueapi_cache.")
        try:
            with os.fdopen(fd, "wb") as token_file:
                token_file.write(
                    base64.b64encode(cache.model_dump_json().encode("utf-8"))
                )
            os.replace(tmp_path, self._file_path)
        except BaseException:
            Path(tmp_path).unlink(missing_ok=True)
            raise

    def load_cache(self) -> Cache:
        self._create_parent_folder_if_necessary()
        with open(self._file_path, "rb") as cache_file:
            return TypeAdapter(Cache).validate_json(
                base64.b64decode(cache_file.read()).decode("utf-8")
            )

    def delete_cache(self) -> None:
        Path(self._file_path).unlink(missing_ok=True)

    def can_access_cache(self) -> bool:
        assert self._token_path
        try:
            self._create_parent_folder_if_necessary()
            self._token_path.write_text("")
        except IsADirectoryError:
            print("Invalid path: a directory path was provided instead of a file path")
            return False
        except PermissionError:
            print(f"Permission denied: Cannot write to {self._token_path.absolute()}")
            return False
        return True

    def _create_parent_folder_if_necessary(self):
        self._token_path.parent.mkdir(parents=True, exist_ok=True)


class SessionManager:
    def __init__(self, server_config: OIDCConfig, cache_manager: CacheManager) -> None:
        self._server_config = server_config
        self._cache_manager: CacheManager = cache_manager

    @classmethod
    def from_cache(
        cls, auth_token_path: Path | None, server_url: str | None = None
    ) -> SessionManager:
        cache_manager = SessionCacheManager(auth_token_path, server_url)
        cache = cache_manager.load_cache()
        return SessionManager(
            server_config=cache.oidc_config, cache_manager=cache_manager
        )

    @property
    def server_config(self) -> OIDCConfig:
        return self._server_config

    def is_for(self, server_config: OIDCConfig) -> bool:
        """
        Whether this session was created for the given OIDC config. If a server
        changes its OIDC config, tokens cached for the old config are useless.
        """
        return self._server_config.model_dump() == server_config.model_dump()

    def delete_cache(self) -> None:
        self._cache_manager.delete_cache()

    def get_valid_access_token(self, rejected_token: str | None = None) -> str:
        """
        Retrieves a valid access token, refreshing it if it is about to expire.

        Args:
            rejected_token: An access token the server has rejected. If the
                cache still holds this token it is refreshed even if it has
                not expired. If another process has already replaced it, the
                newer token is used instead.

        Returns:
            str: A valid access token if successful.
            "": If there is no usable login. The cache is only deleted if it
                is unreadable, or the OIDC provider rejects the refresh token.

        Raises:
            AuthenticationServerUnavailableError: If the token needs refreshing
                but the OIDC provider cannot be reached. The cache is kept.
        """
        try:
            cache = self._cache_manager.load_cache()
        except FileNotFoundError:
            return ""
        except Exception as e:
            LOGGER.warning("Discarding unreadable login cache: %s", e)
            self.delete_cache()
            return ""

        try:
            expires_in = self._seconds_until_expiry(cache.access_token)
        except jwt.InvalidTokenError as e:
            # Not issued for this server's audience/issuer, refreshing cannot
            # change that so the user must log in again
            LOGGER.warning("Cached access token is not usable: %s", e)
            self.delete_cache()
            return ""

        if cache.access_token != rejected_token and (
            expires_in > REFRESH_MARGIN_SECONDS
        ):
            return cache.access_token
        return self._refresh_auth_token(cache)

    def _seconds_until_expiry(self, access_token: str) -> float:
        """
        Check the token belongs to this server's OIDC config and return how long
        it has left. The signature is not verified: the server does that, and
        verifying here would mean every request needs the OIDC provider to be
        reachable (to fetch its signing keys).
        """
        claims = jwt.decode(
            access_token,
            options={
                "verify_signature": False,
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": False,
                "require": ["exp"],
            },
            audience=self._server_config.client_audience,
            issuer=self._server_config.issuer,
        )
        return claims["exp"] - time.time()

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
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            print("Logged out")
        except Exception as e:
            print(
                "An unexpected error occurred while attempting "
                f"to log out from the server.{e}"
            )

    def _refresh_auth_token(self, cache: Cache) -> str:
        """
        Exchange the refresh token for new tokens.

        The existing cache is left untouched until the refresh succeeds, and is
        only deleted if the provider says the refresh token is no longer valid.
        """
        issuer = self._server_config.issuer
        try:
            response = requests.post(
                self._server_config.token_endpoint,
                data={
                    "client_id": self._server_config.client_id,
                    "grant_type": "refresh_token",
                    "refresh_token": cache.refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as e:
            raise AuthenticationServerUnavailableError(
                "Your access token needs refreshing but the authentication server "
                f"({issuer}) could not be reached: {e}. You are still logged in, "
                "please try again once it is reachable."
            ) from e

        if response.status_code == HTTPStatus.OK:
            try:
                token = response.json()
                access_token = token["access_token"]
            except (ValueError, KeyError, TypeError) as e:
                raise AuthenticationServerUnavailableError(
                    "Your access token needs refreshing but the authentication "
                    f"server ({issuer}) returned an unexpected response. You are "
                    "still logged in, please try again later."
                ) from e
            self._cache_manager.save_cache(
                Cache(
                    oidc_config=self._server_config,
                    refresh_token=token.get("refresh_token", cache.refresh_token),
                    id_token=token.get("id_token", cache.id_token),
                    access_token=access_token,
                ),
            )
            return access_token
        error, description = _oauth_error(response)
        if error == "invalid_grant":
            # The refresh token has expired, been revoked, or was issued to a
            # different client. Only now is the login really gone.
            LOGGER.warning(
                "Your login session has expired or been revoked (%s), "
                "please log in again with 'blueapi login'",
                description,
            )
            self.delete_cache()
            return ""
        # Anything else (5xx, invalid_client, ...) is a problem with the
        # authentication server or its configuration, not with this login
        raise AuthenticationServerUnavailableError(
            "Your access token needs refreshing but the authentication server "
            f"({issuer}) returned an error: {response.status_code} {description}. "
            "You are still logged in, please try again later."
        )

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
                timeout=REQUEST_TIMEOUT_SECONDS,
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
            timeout=REQUEST_TIMEOUT_SECONDS,
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


def _oauth_error(response: requests.Response) -> tuple[str | None, str]:
    """The OAuth2 error code (RFC 6749 5.2) and a description of it"""
    try:
        body = response.json()
    except ValueError:
        return None, response.text or response.reason
    if not isinstance(body, dict):
        return None, response.text
    error = body.get("error")
    return error, body.get("error_description") or error or response.text


def migrate_legacy_cache(server_url: str, server_config: OIDCConfig) -> None:
    """
    Move a login cached at the old shared default path to this server's cache
    path, if it was made with this server's OIDC config.
    """
    new_path = default_cache_path(server_url)
    legacy_path = default_cache_path(None)
    if new_path.exists() or not legacy_path.exists():
        return
    try:
        cache = SessionCacheManager(legacy_path).load_cache()
    except Exception:
        return
    if SessionManager(cache.oidc_config, SessionCacheManager(legacy_path)).is_for(
        server_config
    ):
        os.replace(legacy_path, new_path)


class JWTAuth(AuthBase):
    """Adds the bearer token (if any) to requests"""

    def __init__(self, session_manager: SessionManager | None):
        self.token: str = (
            session_manager.get_valid_access_token() if session_manager else ""
        )

    def __call__(self, request):
        if self.token:
            request.headers["Authorization"] = f"Bearer {self.token}"
        return request

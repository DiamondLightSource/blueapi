import os
import stat
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import requests
import responses
from starlette.status import HTTP_403_FORBIDDEN
from tests.conftest import ISSUER, _make_token

from blueapi.client.session import (
    AuthenticationServerUnavailableError,
    SessionCacheManager,
    SessionManager,
    default_cache_path,
    migrate_legacy_cache,
)
from blueapi.config import OIDCConfig
from blueapi.service.model import Cache


@pytest.fixture
def auth_token_path(tmp_path) -> Path:
    return tmp_path / "blueapi_cache"


@pytest.fixture
def session_manager(
    oidc_config: OIDCConfig,
    auth_token_path,
    mock_authn_server: responses.RequestsMock,
) -> SessionManager:
    return SessionManager(
        server_config=oidc_config, cache_manager=SessionCacheManager(auth_token_path)
    )


def test_logout(
    session_manager: SessionManager,
    oidc_config: OIDCConfig,
    cached_valid_token: Path,
    auth_token_path: Path,
):
    assert os.path.exists(auth_token_path)
    session_manager.logout()
    assert not os.path.exists(auth_token_path)


def test_refresh_auth_token(
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    cached_valid_refresh: Path,
    new_token: dict[str, Any],
):
    token = session_manager.get_valid_access_token()
    assert token == new_token["access_token"]


def test_get_empty_token_if_no_cache(session_manager: SessionManager):
    token = session_manager.get_valid_access_token()
    assert token == ""


def test_get_empty_token_if_refresh_fails(
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    cached_expired_refresh: Path,
):
    assert cached_expired_refresh.exists()
    token = session_manager.get_valid_access_token()
    assert token == ""
    assert not cached_expired_refresh.exists()


def test_get_empty_token_if_invalid_cache(
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    cache_with_invalid_audience: Path,
):
    token = session_manager.get_valid_access_token()
    assert token == ""


def test_get_empty_token_if_exception_in_decode(
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    cached_expired_refresh: Path,
):
    assert cached_expired_refresh.exists()
    token = session_manager.get_valid_access_token()
    assert token == ""
    assert not cached_expired_refresh.exists()


def test_poll_for_token(
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    valid_token: dict[str, Any],
    device_code: str,
):
    token = session_manager.poll_for_token(device_code, 1, 2)
    assert token == valid_token


@patch("blueapi.client.session.time.sleep", return_value=None)
def test_poll_for_token_timeout(
    mock_sleep,
    oidc_well_known: dict[str, Any],
    mock_authn_server: responses.RequestsMock,
    session_manager: SessionManager,
    device_code: str,
):
    mock_authn_server.stop()
    mock_authn_server.remove(responses.POST, oidc_well_known["token_endpoint"])
    mock_authn_server.post(
        url=oidc_well_known["token_endpoint"],
        json={"error": "authorization_pending"},
        status=HTTP_403_FORBIDDEN,
    )
    with pytest.raises(TimeoutError), mock_authn_server:
        session_manager.poll_for_token(device_code, 0.01, 0.01)


def test_session_cache_manager_returns_writable_file_path(tmp_path):
    os.environ["XDG_CACHE_HOME"] = str(tmp_path)
    cache = SessionCacheManager(token_path=None)
    Path(cache._file_path).touch()
    assert os.path.isfile(cache._file_path)
    assert cache._file_path == f"{tmp_path}/blueapi_cache"


@pytest.mark.parametrize(
    "server_url,file_name",
    [
        (None, "blueapi_cache"),
        (
            "https://i22-blueapi.diamond.ac.uk",
            "blueapi_cache.i22-blueapi.diamond.ac.uk",
        ),
        ("http://localhost:8000/", "blueapi_cache.localhost_8000"),
        ("http://localhost:8010", "blueapi_cache.localhost_8010"),
    ],
)
def test_default_cache_path_is_per_server(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    server_url: str | None,
    file_name: str,
):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert default_cache_path(server_url) == tmp_path / file_name
    assert SessionCacheManager(None, server_url)._token_path == tmp_path / file_name


def test_explicit_token_path_ignores_server_url(tmp_path: Path):
    path = tmp_path / "my_token"
    assert SessionCacheManager(path, "http://localhost:8000")._token_path == path


def test_save_cache_is_private_and_leaves_no_temp_files(
    session_manager: SessionManager, cached_valid_token: Path, tmp_path: Path
):
    cache_manager = SessionCacheManager(cached_valid_token)
    cache = cache_manager.load_cache()
    cache_manager.save_cache(cache.model_copy(update={"access_token": "updated"}))

    assert cache_manager.load_cache().access_token == "updated"
    assert stat.S_IMODE(cached_valid_token.stat().st_mode) == 0o600
    assert list(tmp_path.iterdir()) == [cached_valid_token]


def test_valid_token_does_not_need_oidc_provider(
    oidc_config: OIDCConfig, cached_valid_token: Path, cached_valid_token_value: str
):
    # No mock_authn_server: any request to the OIDC provider would fail
    session_manager = SessionManager(
        oidc_config, SessionCacheManager(cached_valid_token)
    )
    assert session_manager.get_valid_access_token() == cached_valid_token_value


def _cache_token(
    path: Path, oidc_config: OIDCConfig, rsa_private_key: str, expires_in: float
) -> str:
    token = _make_token("t", -60, expires_in, rsa_private_key, jwt_access_token=True)
    SessionCacheManager(path).save_cache(
        Cache(
            oidc_config=oidc_config,
            access_token=token["access_token"],
            refresh_token=token["refresh_token"],
            id_token=token["id_token"],
        )
    )
    return token["access_token"]


def test_token_about_to_expire_is_refreshed(
    session_manager: SessionManager,
    auth_token_path: Path,
    oidc_config: OIDCConfig,
    rsa_private_key: str,
    new_token: dict[str, Any],
):
    _cache_token(auth_token_path, oidc_config, rsa_private_key, expires_in=20)
    assert session_manager.get_valid_access_token() == new_token["access_token"]


def test_token_not_about_to_expire_is_not_refreshed(
    session_manager: SessionManager,
    auth_token_path: Path,
    oidc_config: OIDCConfig,
    rsa_private_key: str,
):
    token = _cache_token(auth_token_path, oidc_config, rsa_private_key, expires_in=60)
    assert session_manager.get_valid_access_token() == token


def test_rejected_token_is_refreshed(
    session_manager: SessionManager,
    cached_valid_token: Path,
    cached_valid_token_value: str,
    new_token: dict[str, Any],
):
    token = session_manager.get_valid_access_token(
        rejected_token=cached_valid_token_value
    )
    assert token == new_token["access_token"]


def test_rejected_token_already_replaced_by_another_process(
    oidc_config: OIDCConfig,
    cached_valid_token: Path,
    cached_valid_token_value: str,
):
    # No mock_authn_server: a refresh would fail
    session_manager = SessionManager(
        oidc_config, SessionCacheManager(cached_valid_token)
    )
    token = session_manager.get_valid_access_token(rejected_token="an_older_token")
    assert token == cached_valid_token_value


def test_cache_kept_if_oidc_provider_unreachable(
    oidc_config: OIDCConfig, cached_valid_refresh: Path
):
    session_manager = SessionManager(
        oidc_config, SessionCacheManager(cached_valid_refresh)
    )
    with (
        responses.RequestsMock() as mock,
        pytest.raises(
            AuthenticationServerUnavailableError, match="could not be reached"
        ),
    ):
        mock.get(
            ISSUER + "/.well-known/openid-configuration",
            body=requests.ConnectionError("down"),
        )
        session_manager.get_valid_access_token()
    assert cached_valid_refresh.exists()


def test_cache_kept_if_oidc_provider_errors(
    oidc_config: OIDCConfig,
    oidc_well_known: dict[str, Any],
    cached_valid_refresh: Path,
):
    session_manager = SessionManager(
        oidc_config, SessionCacheManager(cached_valid_refresh)
    )
    with (
        responses.RequestsMock() as mock,
        pytest.raises(AuthenticationServerUnavailableError, match="503"),
    ):
        mock.get(ISSUER + "/.well-known/openid-configuration", json=oidc_well_known)
        mock.post(oidc_well_known["token_endpoint"], status=503)
        session_manager.get_valid_access_token()
    assert cached_valid_refresh.exists()


def test_cache_deleted_if_token_for_different_audience(
    session_manager: SessionManager, cache_with_invalid_audience: Path
):
    assert session_manager.get_valid_access_token() == ""
    assert not cache_with_invalid_audience.exists()


def test_is_for(oidc_config: OIDCConfig, session_manager: SessionManager):
    assert session_manager.is_for(oidc_config)
    assert not session_manager.is_for(
        oidc_config.model_copy(update={"client_audience": "other"})
    )


def test_cache_kept_if_refresh_returns_unexpected_body(
    oidc_config: OIDCConfig,
    oidc_well_known: dict[str, Any],
    cached_valid_refresh: Path,
):
    session_manager = SessionManager(
        oidc_config, SessionCacheManager(cached_valid_refresh)
    )
    with (
        responses.RequestsMock() as mock,
        pytest.raises(AuthenticationServerUnavailableError, match="unexpected"),
    ):
        mock.get(ISSUER + "/.well-known/openid-configuration", json=oidc_well_known)
        mock.post(oidc_well_known["token_endpoint"], body="<html>proxy login</html>")
        session_manager.get_valid_access_token()
    assert cached_valid_refresh.exists()


@pytest.mark.parametrize(
    "status,error", [(400, "invalid_client"), (401, "unauthorized_client"), (400, None)]
)
def test_cache_kept_if_refresh_rejected_for_other_reasons(
    oidc_config: OIDCConfig,
    oidc_well_known: dict[str, Any],
    cached_valid_refresh: Path,
    status: int,
    error: str | None,
):
    session_manager = SessionManager(
        oidc_config, SessionCacheManager(cached_valid_refresh)
    )
    with (
        responses.RequestsMock() as mock,
        pytest.raises(AuthenticationServerUnavailableError, match=str(status)),
    ):
        mock.get(ISSUER + "/.well-known/openid-configuration", json=oidc_well_known)
        mock.post(
            oidc_well_known["token_endpoint"],
            status=status,
            json={"error": error} if error else None,
        )
        session_manager.get_valid_access_token()
    assert cached_valid_refresh.exists()


def test_requests_to_oidc_provider_have_timeouts(
    session_manager: SessionManager,
    mock_authn_server: responses.RequestsMock,
    cached_valid_refresh: Path,
    device_code: str,
):
    session_manager.get_valid_access_token()  # refresh
    session_manager.poll_for_token(device_code, 1, 2)
    session_manager.logout()
    assert mock_authn_server.calls
    for call in mock_authn_server.calls:
        timeout = call.request.req_kwargs["timeout"]  # type: ignore[attr-defined]
        assert timeout, call.request.url


def _write_cache(path: Path, oidc_config: OIDCConfig) -> None:
    SessionCacheManager(path).save_cache(
        Cache(
            oidc_config=oidc_config,
            access_token="a",
            refresh_token="r",
            id_token="i",
        )
    )


def test_legacy_cache_migrated_if_for_this_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, oidc_config: OIDCConfig
):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    _write_cache(tmp_path / "blueapi_cache", oidc_config)

    migrate_legacy_cache("http://localhost:8000", oidc_config)

    assert not (tmp_path / "blueapi_cache").exists()
    migrated = SessionCacheManager(tmp_path / "blueapi_cache.localhost_8000")
    assert migrated.load_cache().refresh_token == "r"


def test_legacy_cache_not_migrated_if_for_another_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, oidc_config: OIDCConfig
):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    _write_cache(tmp_path / "blueapi_cache", oidc_config)

    migrate_legacy_cache(
        "http://localhost:8000",
        oidc_config.model_copy(update={"client_audience": "other"}),
    )

    assert (tmp_path / "blueapi_cache").exists()
    assert not (tmp_path / "blueapi_cache.localhost_8000").exists()


def test_legacy_cache_does_not_replace_existing_login(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, oidc_config: OIDCConfig
):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    _write_cache(tmp_path / "blueapi_cache", oidc_config)
    SessionCacheManager(tmp_path / "blueapi_cache.localhost_8000").save_cache(
        Cache(
            oidc_config=oidc_config, access_token="a", refresh_token="new", id_token="i"
        )
    )

    migrate_legacy_cache("http://localhost:8000", oidc_config)

    current = SessionCacheManager(tmp_path / "blueapi_cache.localhost_8000")
    assert current.load_cache().refresh_token == "new"

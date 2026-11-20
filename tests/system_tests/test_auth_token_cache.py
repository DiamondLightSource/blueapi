"""
System tests for how the client caches and reuses OIDC tokens.

The token cache stores the OIDC config of whichever server the user logged in
to. If the client is then used against a server with a different OIDC config
(e.g. the server's config changed, or another beamline's server is used) the
cached config is still trusted: `login()` reports "Logged in" because the
cached token validates against the *cached* config, but the server rejects it.

These tests start their own blueapi server on a different port, using the
already running stack (keycloak etc.) for everything else.
"""

import os
import subprocess
import sys
import time
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import jwt
import pytest
import requests
import yaml
from tests.system_tests.test_blueapi_client import browser_login
from tests.system_tests.test_blueapi_system import _DATA_PATH, User

from blueapi.client import BlueapiClient
from blueapi.client.session import AuthenticationServerUnavailableError, SessionManager

# Port 8000 is the stack's blueapi, 8001 is taken by another stack service
STACK_SERVER_URL = "http://localhost:8000"
OTHER_SERVER_PORT = 8010
OTHER_SERVER_URL = f"http://localhost:{OTHER_SERVER_PORT}"
KEYCLOAK_ISSUER = "http://localhost:8081/realms/master"


@pytest.fixture(scope="module")
def other_server(tmp_path_factory) -> Generator[str]:
    """
    A second blueapi server, sharing the same keycloak, but using a different
    OIDC client/audience to the stack's server on port 8000.
    """
    config = {
        "api": {"url": f"http://0.0.0.0:{OTHER_SERVER_PORT}"},
        "env": {"sources": [{"kind": "planFunctions", "module": "dodal.plans"}]},
        "oidc": {
            "issuer": KEYCLOAK_ISSUER,
            "client_id": "tiled-cli",
            "client_audience": "tiled",
        },
    }
    config_file = tmp_path_factory.mktemp("other_server") / "config.yaml"
    config_file.write_text(yaml.dump(config))
    proc = subprocess.Popen(
        [sys.executable, "-m", "blueapi", "-c", str(config_file), "serve"]
    )
    try:
        for _ in range(120):
            try:
                if requests.get(f"{OTHER_SERVER_URL}/healthz").ok:
                    break
            except requests.ConnectionError:
                pass
            if proc.poll() is not None:
                raise RuntimeError("Second blueapi server exited during startup")
            time.sleep(0.5)
        else:
            raise TimeoutError("Second blueapi server did not start")
        yield OTHER_SERVER_URL
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture
def cache_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Use the default token cache location, but inside a temp dir"""
    # Playwright finds its browsers via XDG_CACHE_HOME, so pin it first
    original_cache = Path(os.environ.get("XDG_CACHE_HOME", "~/.cache")).expanduser()
    monkeypatch.setenv(
        "PLAYWRIGHT_BROWSERS_PATH",
        os.environ.get(
            "PLAYWRIGHT_BROWSERS_PATH", str(original_cache / "ms-playwright")
        ),
    )
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    return tmp_path / "cache"


def client_config(tmp_path: Path, api_url: str) -> Path:
    """Write a CLI config for the given server, using the default token path"""
    config = yaml.safe_load((_DATA_PATH / "config-cli.yaml").read_text())
    config["api"] = {"url": api_url}
    config_file = tmp_path / f"config-{api_url.rsplit(':', 1)[-1]}.yaml"
    config_file.write_text(yaml.dump(config))
    return config_file


def login(config_file: Path, user: User) -> BlueapiClient:
    with patch(
        "blueapi.client.session.webbrowser.open_new_tab",
        side_effect=lambda url: browser_login(url, user),
    ):
        BlueapiClient.from_config_file(str(config_file)).login()
    return BlueapiClient.from_config_file(str(config_file))


def test_login_to_server_with_different_oidc_config(
    tmp_path: Path, cache_home: Path, other_server: str
):
    """
    Logged in to server A, then use server B (with a different OIDC config).

    Currently login() to B says "Logged in" using A's cached token/config, and
    every request to B is then rejected.
    """
    client_a = login(client_config(tmp_path, STACK_SERVER_URL), User.alice)
    assert client_a.get_state()  # sanity check: authenticated against A

    client_b = login(client_config(tmp_path, other_server), User.alice)

    # Fails with UnauthorisedAccessError: the token sent is for 'ixx-blueapi'
    # but server B expects audience 'tiled'
    assert client_b.get_state()

    # Logging in to B should not have logged us out of A
    client_a = BlueapiClient.from_config_file(
        str(client_config(tmp_path, STACK_SERVER_URL))
    )
    assert client_a.get_state()


def test_cache_kept_when_keycloak_unreachable(
    tmp_path: Path, cache_home: Path, monkeypatch: pytest.MonkeyPatch
):
    """
    With an offline_access refresh token the session is long lived, so failing
    to reach keycloak should not throw the cache away.
    """
    login(client_config(tmp_path, STACK_SERVER_URL), User.alice)
    cached_files = list(cache_home.iterdir())
    assert cached_files

    # Route all HTTP traffic (requests and urllib) via a dead proxy so that
    # keycloak (JWKS, token endpoint) cannot be reached
    for var in ("no_proxy", "NO_PROXY"):
        monkeypatch.delenv(var, raising=False)
    for var in ("http_proxy", "HTTP_PROXY"):
        monkeypatch.setenv(var, "http://127.0.0.1:9")

    # A token that is not about to expire is usable without keycloak
    session_manager = SessionManager.from_cache(None, STACK_SERVER_URL)
    token = session_manager.get_valid_access_token()
    assert token

    # Needing a refresh while keycloak is unreachable is a helpful error...
    with pytest.raises(
        AuthenticationServerUnavailableError, match="You are still logged in"
    ):
        session_manager.get_valid_access_token(rejected_token=token)

    # ...and not a silent logout
    assert all(f.exists() for f in cached_files)


def test_access_token_refreshed_before_it_expires(tmp_path: Path, cache_home: Path):
    """
    A token that is about to expire should be refreshed, otherwise it can
    expire between the client checking it and the server validating it.
    """
    login(client_config(tmp_path, STACK_SERVER_URL), User.alice)
    session_manager = SessionManager.from_cache(None, STACK_SERVER_URL)
    token = session_manager.get_valid_access_token()
    expiry = jwt.decode(token, options={"verify_signature": False})["exp"]

    # Wait until the token has less than 30 seconds left (keycloak gives 60s)
    time.sleep(max(0.0, expiry - time.time() - 25))

    new_token = session_manager.get_valid_access_token()
    assert new_token != token
    assert (
        jwt.decode(new_token, options={"verify_signature": False})["exp"] - time.time()
        > 30
    )

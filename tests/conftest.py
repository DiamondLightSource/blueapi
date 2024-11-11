import asyncio
import base64
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

# Based on https://docs.pytest.org/en/latest/example/simple.html#control-skipping-of-tests-according-to-command-line-option  # noqa: E501
import jwt
import pytest
import responses
from bluesky import RunEngine
from bluesky.run_engine import TransitionError
from observability_utils.tracing import JsonObjectSpanExporter, setup_tracing
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import get_tracer_provider

from blueapi.config import CLIClientConfig, OAuthServerConfig


@pytest.fixture(scope="function")
def RE(request):
    loop = asyncio.new_event_loop()
    loop.set_debug(True)
    RE = RunEngine({}, call_returns_result=True, loop=loop)

    def clean_event_loop():
        if RE.state not in ("idle", "panicked"):
            try:
                RE.halt()
            except TransitionError:
                pass
        loop.call_soon_threadsafe(loop.stop)
        RE._th.join()
        loop.close()

    request.addfinalizer(clean_event_loop)
    return RE


@pytest.fixture(scope="session")
def exporter() -> TracerProvider:
    setup_tracing("test", False)
    exporter = JsonObjectSpanExporter()
    provider = cast(TracerProvider, get_tracer_provider())
    # Use SimpleSpanProcessor to keep tests quick
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter


@pytest.fixture
def valid_oidc_url() -> str:
    return "https://auth.example.com/realms/sample/.well-known/openid-configuration"


@pytest.fixture
def oauth_server_config(valid_oidc_url: str) -> OAuthServerConfig:
    return OAuthServerConfig(oidc_config_url=valid_oidc_url)


@pytest.fixture
def oauth_client_config(tmp_path: Path) -> CLIClientConfig:
    return CLIClientConfig(
        client_id="example-client",
        client_audience="example",
        token_file_path=tmp_path / "token",
    )


@pytest.fixture
def valid_auth_config(tmp_path: Path, valid_oidc_url: str) -> str:
    config: str = f"""
oauth_server:
  oidc_config_url: {valid_oidc_url}
oauth_client:
  client_id: client_id
  client_audience: audience
  token_file_path: {tmp_path}/token
"""
    with open(tmp_path / "auth_config.yaml", mode="w") as valid_auth_config_file:
        valid_auth_config_file.write(config)
        return valid_auth_config_file.name


@pytest.fixture
def valid_oidc_config() -> dict[str, Any]:
    return {
        "device_authorization_endpoint": "https://example.com/device_authorization",
        "authorization_endpoint": "https://example.com/authorization",
        "token_endpoint": "https://example.com/token",
        "issuer": "https://example.com",
        "jwks_uri": "https://example.com/realms/master/protocol/openid-connect/certs",
        "end_session_endpoint": "https://example.com/logout",
        "id_token_signing_alg_values_supported": ["RS256", "RS384", "RS512"],
    }


@pytest.fixture
def expired_token(tmp_path: Path) -> Path:
    token_path = tmp_path / "token"
    with open(token_path, "w") as token_file:
        # base64 encoded token
        token_file.write(
            base64.b64encode(
                b'{"access_token":"expired_token","refresh_token":"refresh_token"}'
            ).decode("utf-8")
        )
    return token_path


@pytest.fixture
def valid_token(tmp_path: Path) -> Path:
    token_path = tmp_path / "token"
    with open(token_path, "w") as token_file:
        # base64 encoded token
        token_file.write(
            base64.b64encode(
                b'{"access_token":"token","refresh_token":"refresh_token"}'
            ).decode("utf-8")
        )
    return token_path


@pytest.fixture
def mock_authn_server(valid_oidc_url: str, valid_oidc_config: dict[str, Any]):
    requests_mock = responses.RequestsMock(assert_all_requests_are_fired=True)
    requests_mock.get(valid_oidc_url, json=valid_oidc_config)
    return requests_mock


@pytest.fixture
def mock_decode_jwt() -> Callable[[str], dict[str, Any] | None]:
    def mock_decode(
        token: str, audience: str | Iterable[str] | None = None
    ) -> dict[str, Any] | None:
        if token == "expired_token":
            raise jwt.ExpiredSignatureError
        if token == "token" or token == "new_token":
            return {
                "name": "John Doe",
                "fedid": "jd1",
            }
        return None

    return Mock(side_effect=mock_decode)

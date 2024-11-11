import asyncio
import base64
import json
import time
from pathlib import Path
from typing import Any, cast

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

from blueapi.config import CLIClientConfig


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
def oidc_config(valid_oidc_url: str, tmp_path: Path) -> CLIClientConfig:
    return CLIClientConfig(
        well_known_url=valid_oidc_url,
        client_id="example-client",
        client_audience="example",
        token_file_path=tmp_path / "token",
    )


@pytest.fixture
def valid_auth_config(tmp_path: Path, valid_oidc_url: str) -> str:
    config: str = f"""
oidc_config:
  well_known_url: {valid_oidc_url}
  client_id: "blueapi"
  client_audience: "blueapi-cli"
  token_file_path: {tmp_path / "auth_token"}
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


def _make_token(name: str, issued_in: float, expires_in: float, tmp_path: Path) -> Path:
    token_path = tmp_path / "token"

    now = time.time()

    RSA_key = """-----BEGIN RSA PRIVATE KEY-----
MIIBOgIBAAJBAKj34GkxFhD90vcNLYLInFEX6Ppy1tPf9Cnzj4p4WGeKLs1Pt8Qu
KUpRKfFLfRYC9AIKjbJTWit+CqvjWYzvQwECAwEAAQJAIJLixBy2qpFoS4DSmoEm
o3qGy0t6z09AIJtH+5OeRV1be+N4cDYJKffGzDa88vQENZiRm0GRq6a+HPGQMd2k
TQIhAKMSvzIBnni7ot/OSie2TmJLY4SwTQAevXysE2RbFDYdAiEBCUEaRQnMnbp7
9mxDXDf6AU0cN/RPBjb9qSHDcWZHGzUCIG2Es59z8ugGrDY+pxLQnwfotadxd+Uy
v/Ow5T0q5gIJAiEAyS4RaI9YG8EWx/2w0T67ZUVAw8eOMB6BIUg0Xcu+3okCIBOs
/5OiPgoTdSy7bcF9IGpSE8ZgGKzgYQVZeN97YE00
-----END RSA PRIVATE KEY-----"""

    id_token = {
        "aud": "default-demo",
        "exp": now + expires_in,
        "iat": now + issued_in,
        "iss": "https://example.com",
        "sub": "jd1",
        "name": "Jane Doe",
        "fedid": "jd1",
    }
    response = {
        "access_token": name,
        "token_type": "Bearer",
        "refresh_token": "refresh_token",
        "id_token": f"{jwt.encode(id_token, key=RSA_key, algorithm="RS256")}",
    }
    with open(token_path, "w") as token_file:
        token_file.write(
            base64.b64encode(json.dumps(response).encode("utf-8")).decode("utf-8")
        )
    return token_path


@pytest.fixture
def expired_token(tmp_path: Path) -> Path:
    return _make_token("expired_token", -3600, -1800, tmp_path)


@pytest.fixture
def valid_token(tmp_path: Path) -> Path:
    return _make_token("expired_token", -1800, +1800, tmp_path)


@pytest.fixture
def mock_authn_server(valid_oidc_url: str, valid_oidc_config: dict[str, Any]):
    requests_mock = responses.RequestsMock(assert_all_requests_are_fired=True)
    requests_mock.get(valid_oidc_url, json=valid_oidc_config)
    requests_mock.get(valid_oidc_config["jwks_uri"], json="")
    return requests_mock

import asyncio
import base64
import os
import time
from collections.abc import Iterable
from pathlib import Path
from textwrap import dedent
from typing import Any, cast
from unittest.mock import Mock, patch

# Based on https://docs.pytest.org/en/latest/example/simple.html#control-skipping-of-tests-according-to-command-line-option  # noqa: E501
import jwt
import pytest
import responses
import yaml
from bluesky._vendor.super_state_machine.errors import TransitionError  # type: ignore
from bluesky.run_engine import RunEngine
from fastapi import status
from jwcrypto.jwk import JWK
from observability_utils.tracing import JsonObjectSpanExporter, setup_tracing
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import get_tracer_provider
from responses.matchers import json_params_matcher

from blueapi.config import ApplicationConfig, OIDCConfig
from blueapi.service.model import Cache


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
def exporter() -> JsonObjectSpanExporter:
    setup_tracing("test", False)
    exporter = JsonObjectSpanExporter()
    provider = cast(TracerProvider, get_tracer_provider())
    # Use SimpleSpanProcessor to keep tests quick
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter


@pytest.fixture
def oidc_url() -> str:
    return (
        "https://auth.example.com/realms/master/oidc/.well-known/openid-configuration"
    )


@pytest.fixture
def oidc_config(oidc_url: str) -> OIDCConfig:
    return OIDCConfig(
        well_known_url=oidc_url, client_id="blueapi-cli", client_audience="blueapi"
    )


CACHE_FILE = "blueapi_cache"


@pytest.fixture
def config_with_auth(tmp_path: Path) -> str:
    config = ApplicationConfig(auth_token_path=tmp_path / CACHE_FILE)
    config_path = tmp_path / "auth_config.yaml"
    with open(config_path, mode="w") as valid_auth_config_file:
        valid_auth_config_file.write(yaml.dump(config.model_dump()))
    return config_path.as_posix()


@pytest.fixture
def oidc_well_known() -> dict[str, Any]:
    return {
        "device_authorization_endpoint": "https://example.com/device_authorization",
        "authorization_endpoint": "https://example.com/authorization",
        "token_endpoint": "https://example.com/token",
        "issuer": "https://example.com",
        "jwks_uri": "https://example.com/realms/master/protocol/openid-connect/certs",
        "end_session_endpoint": "https://example.com/end_session",
        "id_token_signing_alg_values_supported": ["RS256"],
    }


@pytest.fixture(scope="session")
def json_web_keyset() -> JWK:
    return JWK.generate(kty="RSA", size=1024, kid="secret", use="sig", alg="RS256")


@pytest.fixture(scope="session")
def rsa_private_key(json_web_keyset: JWK) -> str:
    return json_web_keyset.export_to_pem("private_key", password=None).decode("utf-8")  # type: ignore


def _make_token(
    name: str,
    issued_in: float,
    expires_in: float,
    rsa_private_key: str,
    jwt_access_token: bool = False,
    valid_audience: bool = True,
) -> dict[str, str]:
    now = time.time()

    dummy_token = {
        "aud": "blueapi" if valid_audience else "invalid_audience",
        "exp": now + expires_in,
        "iat": now + issued_in,
        "iss": "https://example.com",
        "sub": "jd1",
        "name": "Jane Doe",
        "fedid": "jd1",
    }
    jwt_token_encoded = jwt.encode(
        dummy_token,
        key=rsa_private_key,
        algorithm="RS256",
        headers={"kid": "secret"},
    )
    response = {
        "access_token": jwt_token_encoded if jwt_access_token else name,
        "token_type": "Bearer",
        "refresh_token": "refresh_token",
        "id_token": jwt_token_encoded,
    }
    return response


@pytest.fixture
def cached_valid_refresh(
    tmp_path: Path, expired_token: dict[str, Any], oidc_config: OIDCConfig
) -> Path:
    cache = Cache(
        oidc_config=oidc_config,
        access_token=expired_token["access_token"],
        refresh_token=expired_token["refresh_token"],
        id_token=expired_token["id_token"],
    )
    with open(cache_path := tmp_path / CACHE_FILE, "xb") as cache_file:
        cache_file.write(base64.b64encode(cache.model_dump_json().encode("utf-8")))
    return cache_path


@pytest.fixture
def cached_expired_refresh(
    tmp_path: Path, expired_token: dict[str, Any], oidc_config: OIDCConfig
) -> Path:
    cache = Cache(
        oidc_config=oidc_config,
        access_token=expired_token["access_token"],
        refresh_token="expired_refresh",
        id_token=expired_token["id_token"],
    )
    with open(cache_path := tmp_path / CACHE_FILE, "xb") as cache_file:
        cache_file.write(base64.b64encode(cache.model_dump_json().encode("utf-8")))
    return cache_path


@pytest.fixture
def cached_valid_token(
    tmp_path: Path, valid_token_with_jwt: dict[str, Any], oidc_config: OIDCConfig
) -> Path:
    cache = Cache(
        oidc_config=oidc_config,
        access_token=valid_token_with_jwt["access_token"],
        refresh_token=valid_token_with_jwt["refresh_token"],
        id_token=valid_token_with_jwt["id_token"],
    )
    with open(cache_path := tmp_path / CACHE_FILE, "xb") as cache_file:
        cache_file.write(base64.b64encode(cache.model_dump_json().encode("utf-8")))
    return cache_path


@pytest.fixture
def cache_with_invalid_audience(
    tmp_path: Path,
    oidc_config: OIDCConfig,
    valid_token_with_jwt_invalid_audience: dict[str, Any],
) -> Path:
    cache = Cache(
        oidc_config=oidc_config,
        access_token=valid_token_with_jwt_invalid_audience["access_token"],
        refresh_token=valid_token_with_jwt_invalid_audience["refresh_token"],
        id_token=valid_token_with_jwt_invalid_audience["id_token"],
    )
    with open(cache_path := tmp_path / CACHE_FILE, "xb") as cache_file:
        cache_file.write(base64.b64encode(cache.model_dump_json().encode("utf-8")))
    return cache_path


@pytest.fixture
def expired_token(rsa_private_key: str) -> dict[str, Any]:
    return _make_token(
        "expired_token", -3600, -1800, rsa_private_key, jwt_access_token=True
    )


@pytest.fixture
def valid_token(rsa_private_key: str) -> dict[str, Any]:
    return _make_token("valid_token", -900, +900, rsa_private_key)


@pytest.fixture
def valid_token_with_jwt(rsa_private_key: str) -> dict[str, Any]:
    return _make_token(
        "valid_token", -900, +900, rsa_private_key, jwt_access_token=True
    )


@pytest.fixture
def valid_token_with_jwt_invalid_audience(rsa_private_key: str) -> dict[str, Any]:
    return _make_token(
        "valid_token",
        -900,
        +900,
        rsa_private_key,
        jwt_access_token=True,
        valid_audience=False,
    )


@pytest.fixture
def new_token(rsa_private_key: str) -> dict[str, Any]:
    return _make_token("new_token", -100, +1700, rsa_private_key)


@pytest.fixture
def device_code() -> str:
    return "ff83j3dk"


@pytest.fixture
def mock_authn_server(
    oidc_url: str,
    oidc_well_known: dict[str, Any],
    oidc_config: OIDCConfig,
    valid_token: dict[str, Any],
    new_token: dict[str, Any],
    device_code: str,
    mock_jwks_fetch,
):
    requests_mock = responses.RequestsMock(assert_all_requests_are_fired=False)
    requests_mock.get(
        "http://localhost:8000/config/oidc",
        json=oidc_config.model_dump(),
    )
    # Fetch well-known OIDC flow URLs from server
    requests_mock.get(oidc_url, json=oidc_well_known)
    # When device flow begins, return a device_code
    requests_mock.post(
        oidc_well_known["device_authorization_endpoint"],
        json={
            "device_code": device_code,
            "verification_uri_complete": oidc_well_known["issuer"] + "/verify",
            "expires_in": 30,
            "interval": 5,
        },
    )

    # When polled with device_code return token
    requests_mock.post(
        oidc_well_known["token_endpoint"],
        json=valid_token,
        match=[
            responses.matchers.urlencoded_params_matcher(
                {
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                    "client_id": oidc_config.client_id,
                }
            ),
        ],
    )
    # When asked to refresh with refresh_token return refreshed token
    requests_mock.post(
        oidc_well_known["token_endpoint"],
        json=new_token,
        match=[
            responses.matchers.urlencoded_params_matcher(
                {
                    "client_id": oidc_config.client_id,
                    "grant_type": "refresh_token",
                    "refresh_token": "refresh_token",
                },
            )
        ],
    )
    # When asked to refresh with invalid refresh token return 400 BAD REQUEST
    requests_mock.post(
        oidc_well_known["token_endpoint"],
        status=400,
        match=[
            responses.matchers.urlencoded_params_matcher(
                {
                    "client_id": oidc_config.client_id,
                    "grant_type": "refresh_token",
                    "refresh_token": "expired_refresh",
                },
            )
        ],
    )
    # When asked to logout using end_session_endpoint return 200 OK
    requests_mock.get(oidc_well_known["end_session_endpoint"], json="")

    with mock_jwks_fetch, requests_mock:
        yield requests_mock


@pytest.fixture
def mock_unauthenticated_server():
    requests_mock = responses.RequestsMock(assert_all_requests_are_fired=False)
    requests_mock.get(
        "http://localhost:8000/config/oidc", status=status.HTTP_204_NO_CONTENT
    )
    with requests_mock:
        yield requests_mock


@pytest.fixture
def mock_jwks_fetch(json_web_keyset: JWK):
    mock = Mock(return_value={"keys": [json_web_keyset.export_public(as_dict=True)]})
    return patch("jwt.PyJWKClient.fetch_data", mock)


# Prevent pytest from catching exceptions when debugging in vscode so that break on
# exception works correctly (see: https://github.com/pytest-dev/pytest/issues/7409)
if os.getenv("PYTEST_RAISE", "0") == "1":

    @pytest.hookimpl(tryfirst=True)
    def pytest_exception_interact(call: pytest.CallInfo[Any]):
        if call.excinfo is not None:
            raise call.excinfo.value
        else:
            raise RuntimeError(
                f"{call} has no exception data, an unknown error has occurred"
            )

    @pytest.hookimpl(tryfirst=True)
    def pytest_internalerror(excinfo: pytest.ExceptionInfo[Any]):
        raise excinfo.value


@pytest.fixture(scope="module")
def mock_numtracker_server() -> Iterable[responses.RequestsMock]:
    query_working = {
        "query": dedent("""
            mutation{
                scan(
                    instrument: "p46",
                    instrumentSession: "ab123"
                    ) {
                    directory{
                        instrumentSession
                        instrument
                        path
                    }
                    scanFile
                    scanNumber
                }
            }
            """)
    }
    query_400 = {
        "query": dedent("""
            mutation{
                scan(
                    instrument: "p47",
                    instrumentSession: "ab123"
                    ) {
                    directory{
                        instrumentSession
                        instrument
                        path
                    }
                    scanFile
                    scanNumber
                }
            }
            """)
    }
    query_500 = {
        "query": dedent("""
            mutation{
                scan(
                    instrument: "p48",
                    instrumentSession: "ab123"
                    ) {
                    directory{
                        instrumentSession
                        instrument
                        path
                    }
                    scanFile
                    scanNumber
                }
            }
            """)
    }
    query_key_error = {
        "query": dedent("""
            mutation{
                scan(
                    instrument: "p49",
                    instrumentSession: "ab123"
                    ) {
                    directory{
                        instrumentSession
                        instrument
                        path
                    }
                    scanFile
                    scanNumber
                }
            }
            """)
    }

    working_response = {
        "data": {
            "scan": {
                "scanFile": "p46-11",
                "scanNumber": 11,
                "directory": {
                    "instrument": "p46",
                    "instrumentSession": "ab123",
                    "path": "/exports/mybeamline/data/2025",
                },
            }
        }
    }
    empty_response = {}

    with responses.RequestsMock(assert_all_requests_are_fired=False) as requests_mock:
        requests_mock.add(
            responses.POST,
            url="https://numtracker-example.com/graphql",
            match=[json_params_matcher(query_working)],
            status=200,
            json=working_response,
        )
        requests_mock.add(
            responses.POST,
            url="https://numtracker-example.com/graphql",
            match=[json_params_matcher(query_400)],
            status=400,
            json=empty_response,
        )
        requests_mock.add(
            responses.POST,
            url="https://numtracker-example.com/graphql",
            match=[json_params_matcher(query_500)],
            status=500,
            json=empty_response,
        )
        requests_mock.add(
            responses.POST,
            url="https://numtracker-example.com/graphql",
            match=[json_params_matcher(query_key_error)],
            status=200,
            json=empty_response,
        )
        yield requests_mock

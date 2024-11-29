from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import responses

from blueapi.client.rest import BlueapiRestClient, BlueskyRemoteControlError
from blueapi.config import OIDCConfig
from blueapi.service.authentication import SessionCacheManager, SessionManager
from blueapi.service.model import EnvironmentResponse


@pytest.fixture
def rest() -> BlueapiRestClient:
    return BlueapiRestClient()


@pytest.fixture
def rest_with_auth(oidc_config: OIDCConfig, tmp_path) -> BlueapiRestClient:
    return BlueapiRestClient(
        session_manager=SessionManager(
            server_config=oidc_config,
            cache_manager=SessionCacheManager(tmp_path / "blueapi_cache"),
        )
    )


@pytest.mark.parametrize(
    "code,expected_exception",
    [
        (404, KeyError),
        (401, BlueskyRemoteControlError),
        (450, BlueskyRemoteControlError),
        (500, BlueskyRemoteControlError),
    ],
)
@patch("blueapi.client.rest.requests.request")
def test_rest_error_code(
    mock_request: Mock,
    rest: BlueapiRestClient,
    code: int,
    expected_exception: type[Exception],
):
    response = Mock()
    response.status_code = code
    mock_request.return_value = response
    with pytest.raises(expected_exception):
        rest.get_plans()


def test_auth_request_functionality(
    rest_with_auth: BlueapiRestClient,
    mock_authn_server: responses.RequestsMock,
    cached_valid_token: Path,
):
    mock_authn_server.stop()  # Cannot use multiple RequestsMock context manager
    mock_get_env = mock_authn_server.get(
        "http://localhost:8000/environment",
        json=EnvironmentResponse(initialized=True).model_dump(),
        status=200,
    )
    result = None
    with mock_authn_server:
        result = rest_with_auth.get_environment()
    assert result == EnvironmentResponse(initialized=True)
    calls = mock_get_env.calls
    assert len(calls) == 1
    cacheManager = SessionCacheManager(cached_valid_token)
    cache = cacheManager.load_cache()
    assert calls[0].request.headers["Authorization"] == f"Bearer {cache.access_token}"


def test_refresh_if_signature_expired(
    rest_with_auth: BlueapiRestClient,
    mock_authn_server: responses.RequestsMock,
    cached_valid_refresh: Path,
):
    mock_authn_server.stop()  # Cannot use multiple RequestsMock context manager
    mock_get_env = mock_authn_server.get(
        "http://localhost:8000/environment",
        json=EnvironmentResponse(initialized=True).model_dump(),
        status=200,
    )
    result = None
    with mock_authn_server:
        result = rest_with_auth.get_environment()
    assert result == EnvironmentResponse(initialized=True)
    calls = mock_get_env.calls
    assert len(calls) == 1
    assert calls[0].request.headers["Authorization"] == "Bearer new_token"

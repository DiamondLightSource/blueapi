import uuid
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests
import responses

from blueapi.client.rest import (
    BlueapiRestClient,
    BlueskyRemoteControlError,
    BlueskyRequestError,
    InvalidParameters,
    ParameterError,
    UnauthorisedAccess,
    UnknownPlan,
    _create_task_exceptions,
)
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


@pytest.mark.parametrize(
    "code,content,expected_exception",
    [
        (200, None, None),
        (401, None, UnauthorisedAccess()),
        (403, None, UnauthorisedAccess()),
        (404, None, UnknownPlan()),
        (
            422,
            """{
                "detail": [{
                    "loc": ["body", "params", "foo"],
                    "type": "missing",
                    "msg": "missing value for foo",
                    "input": {}
                }]
            }""",
            InvalidParameters(
                [
                    ParameterError(
                        loc=["body", "params", "foo"],
                        type="missing",
                        msg="missing value for foo",
                        input={},
                    )
                ]
            ),
        ),
        (450, "non-standard", BlueskyRequestError(450, "non-standard")),
        (500, "internal_error", BlueskyRequestError(500, "internal_error")),
    ],
)
def test_create_task_exceptions(
    code: int, content: str | None, expected_exception: Exception
):
    response = Mock(spec=requests.Response)
    response.status_code = code
    response.text = content
    import json

    response.json.side_effect = lambda: json.loads(content) if content else None
    err = _create_task_exceptions(response)
    assert isinstance(err, type(expected_exception))
    if expected_exception is not None:
        assert err.args == expected_exception.args


def test_auth_request_functionality(
    rest_with_auth: BlueapiRestClient,
    mock_authn_server: responses.RequestsMock,
    cached_valid_token: Path,
):
    environment_id = uuid.uuid4()
    mock_authn_server.stop()  # Cannot use multiple RequestsMock context manager
    mock_get_env = mock_authn_server.get(
        "http://localhost:8000/environment",
        json=EnvironmentResponse(
            environment_id=environment_id, initialized=True
        ).model_dump(mode="json"),
        status=200,
    )
    result = None
    with mock_authn_server:
        result = rest_with_auth.get_environment()
    assert result == EnvironmentResponse(
        environment_id=environment_id, initialized=True
    )
    calls = mock_get_env.calls
    assert len(calls) == 1
    cache_manager = SessionCacheManager(cached_valid_token)
    cache = cache_manager.load_cache()
    assert calls[0].request.headers["Authorization"] == f"Bearer {cache.access_token}"


def test_refresh_if_signature_expired(
    rest_with_auth: BlueapiRestClient,
    mock_authn_server: responses.RequestsMock,
    cached_valid_refresh: Path,
):
    environment_id = uuid.uuid4()
    mock_authn_server.stop()  # Cannot use multiple RequestsMock context manager
    mock_get_env = mock_authn_server.get(
        "http://localhost:8000/environment",
        json=EnvironmentResponse(
            environment_id=environment_id, initialized=True
        ).model_dump(mode="json"),
        status=200,
    )
    result = None
    with mock_authn_server:
        result = rest_with_auth.get_environment()
    assert result == EnvironmentResponse(
        environment_id=environment_id, initialized=True
    )
    calls = mock_get_env.calls
    assert len(calls) == 1
    assert calls[0].request.headers["Authorization"] == "Bearer new_token"


def test_parameter_error_field():
    p1 = ParameterError(
        loc=["body", "parameters", "detectors", 0],
        msg="error message",
        type="error_type",
        input="original_input",
    )
    assert p1.field() == "detectors.0"


def test_parameter_error_missing_string():
    p1 = ParameterError(
        loc=["body", "parameters", "field_one", 0],
        msg="error_message",
        type="missing",
        input=None,
    )
    assert str(p1) == "Missing value for 'field_one.0'"


def test_parameter_error_extra_string():
    p1 = ParameterError(
        loc=["body", "parameters", "foo"],
        msg="error_message",
        type="extra_forbidden",
        input={"foo": "bar"},
    )
    assert str(p1) == "Unexpected field 'foo'"


def test_parameter_error_other_string():
    p1 = ParameterError(
        loc=["body", "parameters", "field_one", 0],
        msg="error_message",
        type="string_value",
        input=34,
    )
    assert str(p1) == "Invalid value 34 for field field_one.0: error_message"

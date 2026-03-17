import uuid
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests
import responses
from packaging.version import Version

from blueapi import __version__
from blueapi.client.rest import (
    BlueapiRestClient,
    BlueskyRemoteControlError,
    BlueskyRequestError,
    InvalidParametersError,
    NotFoundError,
    ParameterError,
    UnauthorisedAccessError,
    UnknownPlanError,
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
        (404, NotFoundError),
        (401, UnauthorisedAccessError),
        (403, UnauthorisedAccessError),
        (450, BlueskyRemoteControlError),
        (500, BlueskyRemoteControlError),
    ],
)
@patch("blueapi.client.rest.requests.Session.request")
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
        (
            401,
            "unauthorised access",
            UnauthorisedAccessError(401, "unauthorised access"),
        ),
        (403, "Forbidden", UnauthorisedAccessError(403, "Forbidden")),
        (
            404,
            "Plan '{name}' was not recognised",
            UnknownPlanError(404, "Plan '{name}' was not recognised"),
        ),
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
            InvalidParametersError(
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
        (
            422,
            '{"detail": "not a list"}',
            BlueskyRequestError(422, ""),
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
    if isinstance(expected_exception, InvalidParametersError):
        assert isinstance(err, InvalidParametersError)
        assert err.errors == expected_exception.errors
    elif expected_exception is not None:
        assert err.args[0] == code
        if content is not None:
            assert err.args[1] == content


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


@pytest.mark.parametrize(
    "server_version,logging_warning_present",
    [(__version__, False), ("0.0.1", True), (None, False)],
)
@patch("blueapi.client.rest.TypeAdapter")
@patch("blueapi.client.rest.requests.Session.request")
@patch("blueapi.client.rest.LOGGER")
def test_server_and_client_versions(
    mock_logger: MagicMock,
    mock_request: Mock,
    mock_type_adapter: Mock,
    rest: BlueapiRestClient,
    server_version: str,
    logging_warning_present: bool,
):
    response = Mock(spec=requests.Response)
    response.status_code = 200
    response.headers = {"x-blueapi-version": server_version}
    mock_request.return_value = response

    rest.get_plans()

    if logging_warning_present:
        mock_logger.warning.assert_called_once_with(
            f"Version mismatch: Blueapi server version is "
            f"{Version(server_version).base_version} "
            f"but client version is {Version(__version__).base_version}. "
            f"Some features may not work as expected."
        )
    else:
        mock_logger.assert_not_called()

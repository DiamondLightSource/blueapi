from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
import responses
from pydantic import BaseModel

from blueapi.client.rest import BlueapiRestClient, BlueskyRemoteControlError
from blueapi.config import CLIClientConfig, OAuthServerConfig
from blueapi.core.bluesky_types import Plan
from blueapi.service.authentication import SessionManager
from blueapi.service.model import PlanModel, PlanResponse


@pytest.fixture
def rest() -> BlueapiRestClient:
    return BlueapiRestClient()


@pytest.fixture
def rest_with_auth(valid_oidc_url: str, tmp_path: Path) -> BlueapiRestClient:
    session_manager = SessionManager(
        server_config=OAuthServerConfig(oidc_config_url=valid_oidc_url),
        client_config=CLIClientConfig(
            client_id="foo", client_audience="bar", token_file_path=tmp_path / "token"
        ),
    )
    return BlueapiRestClient(session_manager=session_manager)


@pytest.mark.parametrize(
    "code,expected_exception",
    [
        (404, KeyError),
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


class MyModel(BaseModel):
    id: str


def test_auth_request_functionality(
    rest_with_auth: BlueapiRestClient,
    valid_token: Path,
    mock_decode_jwt: Callable[[str], dict[str, Any] | None],
):
    plan = Plan(name="my-plan", model=MyModel)
    mock_server = responses.RequestsMock()
    mock_server.get(
        "http://localhost:8000/plans",
        json=PlanResponse(plans=[PlanModel.from_plan(plan)]).model_dump(),
    )
    with (
        patch("blueapi.service.Authenticator.decode_jwt", mock_decode_jwt),
        mock_server,
    ):
        result = rest_with_auth.get_plans()
    mock_decode_jwt.assert_called_once_with("token", "bar")
    assert result == PlanResponse(plans=[PlanModel.from_plan(plan)])


def test_refresh_if_signature_expired(
    rest_with_auth: BlueapiRestClient,
    mock_authn_server: responses.RequestsMock,
    mock_decode_jwt: Callable[[str], dict[str, Any] | None],
    expired_token: Path,
):
    mock_authn_server.post(
        "https://example.com/token",
        json={"access_token": "new_token"},
    )
    plan = Plan(name="my-plan", model=MyModel)

    mock_get_plans = (
        mock_authn_server.get(  # Cannot use more than 1 RequestsMock context manager
            "http://localhost:8000/plans",
            json=PlanResponse(plans=[PlanModel.from_plan(plan)]).model_dump(),
        )
    )
    with (
        patch("blueapi.service.Authenticator.decode_jwt", mock_decode_jwt),
        mock_authn_server,
    ):
        result = rest_with_auth.get_plans()
    mock_decode_jwt.assert_called_once_with("expired_token", "bar")
    assert result == PlanResponse(plans=[PlanModel.from_plan(plan)])
    calls = mock_get_plans.calls
    assert len(calls) == 1
    assert calls[0].request.headers["Authorization"] == "Bearer new_token"

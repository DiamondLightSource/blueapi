from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import responses
from pydantic import BaseModel

from blueapi.client.rest import BlueapiRestClient, BlueskyRemoteControlError
from blueapi.config import OIDCConfig
from blueapi.core.bluesky_types import Plan
from blueapi.service.authentication import SessionManager
from blueapi.service.model import PlanModel, PlanResponse


@pytest.fixture
def rest() -> BlueapiRestClient:
    return BlueapiRestClient()


@pytest.fixture
def rest_with_auth(oidc_config: OIDCConfig) -> BlueapiRestClient:
    return BlueapiRestClient(session_manager=SessionManager(oidc_config))


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
    mock_authn_server: responses.RequestsMock,
    cached_valid_token: Path,
):
    plan = Plan(name="my-plan", model=MyModel)
    mock_authn_server.stop()  # Cannot use multiple RequestsMock context manager
    mock_authn_server.get(
        "http://localhost:8000/plans",
        json=PlanResponse(plans=[PlanModel.from_plan(plan)]).model_dump(),
    )
    with mock_authn_server:
        result = rest_with_auth.get_plans()
    assert result == PlanResponse(plans=[PlanModel.from_plan(plan)])


def test_refresh_if_signature_expired(
    rest_with_auth: BlueapiRestClient,
    mock_authn_server: responses.RequestsMock,
    cached_expired_token: Path,
):
    plan = Plan(name="my-plan", model=MyModel)

    mock_authn_server.stop()
    mock_get_plans = (
        mock_authn_server.get(  # Cannot use multiple RequestsMock context manager
            "http://localhost:8000/plans",
            json=PlanResponse(plans=[PlanModel.from_plan(plan)]).model_dump(),
        )
    )
    with mock_authn_server:
        result = rest_with_auth.get_plans()
    assert result == PlanResponse(plans=[PlanModel.from_plan(plan)])
    calls = mock_get_plans.calls
    assert len(calls) == 1
    assert calls[0].request.headers["Authorization"] == "Bearer new_token"

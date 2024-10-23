import base64
from pathlib import Path
from unittest.mock import Mock, patch

import jwt
import pytest
import responses
from pydantic import BaseModel

from blueapi.client.rest import BlueapiRestClient, BlueskyRemoteControlError
from blueapi.config import OAuthClientConfig, OAuthServerConfig
from blueapi.core.bluesky_types import Plan
from blueapi.service.authentication import CliTokenManager, SessionManager
from blueapi.service.model import PlanModel, PlanResponse


@pytest.fixture
def rest() -> BlueapiRestClient:
    return BlueapiRestClient()


@pytest.fixture
@responses.activate
def rest_with_auth(tmp_path: Path) -> BlueapiRestClient:
    responses.add(
        responses.GET,
        "http://example.com",
        json={
            "device_authorization_endpoint": "https://example.com/device_authorization",
            "authorization_endpoint": "https://example.com/authorization",
            "token_endpoint": "https://example.com/token",
            "issuer": "https://example.com",
            "jwks_uri": "https://example.com/realms/master/protocol/openid-connect/certs",
            "end_session_endpoint": "https://example.com/logout",
            "id_token_signing_alg_values_supported": ["RS256", "RS384", "RS512"],
        },
        status=200,
    )
    with open(tmp_path / "token", "w") as token_file:
        # base64 encoded token
        token_file.write(
            base64.b64encode(
                b'{"access_token":"token","refresh_token":"refresh_token"}'
            ).decode("utf-8")
        )
    session_manager = SessionManager(
        token_manager=CliTokenManager(tmp_path / "token"),
        client_config=OAuthClientConfig(client_id="foo", client_audience="bar"),
        server_config=OAuthServerConfig(oidc_config_url="http://example.com"),
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


@responses.activate
def test_auth_request_functionality(rest_with_auth: BlueapiRestClient):
    plan = Plan(name="my-plan", model=MyModel)
    responses.add(
        responses.GET,
        "http://localhost:8000/plans",
        json=PlanResponse(plans=[PlanModel.from_plan(plan)]).model_dump(),
        status=200,
    )
    with patch("blueapi.service.Authenticator.decode_jwt") as mock_decode_jwt:
        mock_decode_jwt.return_value = {"name": "John Doe", "fedid": "jd1"}

        result = rest_with_auth.get_plans()
        mock_decode_jwt.assert_called_once_with("token")
        assert result == PlanResponse(plans=[PlanModel.from_plan(plan)])


@responses.activate
def test_refresh_if_signature_expired(rest_with_auth: BlueapiRestClient):
    plan = Plan(name="my-plan", model=MyModel)
    responses.add(
        responses.GET,
        "http://localhost:8000/plans",
        json=PlanResponse(plans=[PlanModel.from_plan(plan)]).model_dump(),
        status=200,
    )
    with (
        patch("blueapi.service.Authenticator.decode_jwt") as mock_decode_token,
        patch(
            "blueapi.service.SessionManager.refresh_auth_token"
        ) as mock_refresh_token,
    ):
        mock_decode_token.side_effect = jwt.ExpiredSignatureError
        mock_refresh_token.return_value = {"access_token": "new_token"}
        result = rest_with_auth.get_plans()
        mock_decode_token.assert_called_once_with("token")
        mock_refresh_token.assert_called_once()
        assert result == PlanResponse(plans=[PlanModel.from_plan(plan)])

from unittest.mock import MagicMock, Mock, patch

import pytest

from blueapi.client.rest import BlueapiRestClient, BlueskyRemoteControlError


@pytest.fixture
def rest() -> BlueapiRestClient:
    return BlueapiRestClient()


@pytest.mark.parametrize(
    "code,expected_exception",
    [
        (404, KeyError),
        (450, BlueskyRemoteControlError),
        (500, BlueskyRemoteControlError),
    ],
)
@patch("blueapi.client.rest.requests.request")
@patch("blueapi.client.rest.Authentication", autospec=True)
def test_rest_error_code(
    mock_auth: MagicMock,
    mock_request: Mock,
    rest: BlueapiRestClient,
    code: int,
    expected_exception: type[Exception],
):
    mock_auth_instance = mock_auth.return_value
    mock_auth_instance.token = {"access_token": "test_token"}
    mock_auth_instance.verify_token.return_value = (True, None)
    response = Mock()
    response.status_code = code
    mock_request.return_value = response
    with pytest.raises(expected_exception):
        rest.get_plans()

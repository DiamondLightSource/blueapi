from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel

from blueapi.client.rest import BlueapiRestClient, BlueskyRemoteControlError


@pytest.fixture
def rest() -> BlueapiRestClient:
    return BlueapiRestClient()


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


class MyModel(BaseModel):
    id: str

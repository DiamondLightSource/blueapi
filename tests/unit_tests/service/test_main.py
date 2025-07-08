from unittest import mock
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from blueapi.service.main import get_passthrough_headers, log_request_details


async def test_log_request_details():
    with mock.patch("blueapi.service.main.LOGGER") as logger:
        app = FastAPI()
        app.middleware("http")(log_request_details)

        @app.get("/")
        async def root():
            return {"message": "Hello World"}

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        logger.info.assert_called_once_with(
            "method: GET url: http://testserver/ body: b''"
        )


@pytest.mark.parametrize(
    "headers, expected_headers",
    [
        ({}, {}),
        ({"foo": "bar"}, {}),
        ({"authorization": "yes"}, {"authorization": "yes"}),
        ({"autHORIzation": "yes"}, {"autHORIzation": "yes"}),
        ({"autHORIzation": "yes", "foo": "bar"}, {"autHORIzation": "yes"}),
        ({"autHORIzation": ""}, {"autHORIzation": ""}),
    ],
)
def test_get_passthrough_headers(
    headers: dict[str, str], expected_headers: dict[str, str]
):
    request = Mock(spec=Request)
    request.headers = headers
    assert get_passthrough_headers(request) == expected_headers

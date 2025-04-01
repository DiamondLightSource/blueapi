from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from blueapi.service.main import log_request_details


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

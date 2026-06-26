from unittest import mock
from unittest.mock import Mock, call, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from blueapi import __version__
from blueapi.config import ApplicationConfig
from blueapi.service.main import (
    get_passthrough_headers,
    lifespan,
    log_request_details,
)
from blueapi.service.middleware import VersionHeaders


async def test_add_version_header():
    app = FastAPI()
    app.add_middleware(VersionHeaders)

    @app.get("/")
    async def root():
        return {"message": "Hello World"}

    client = TestClient(app)
    response = client.get("/")

    assert response.headers["X-API-VERSION"] == ApplicationConfig.REST_API_VERSION
    assert response.headers["X-BlueAPI-VERSION"] == __version__


@pytest.mark.parametrize("path,level", [("/", "info"), ("/healthz", "debug")])
async def test_log_request_details(path: str, level: str):
    with mock.patch("blueapi.service.main.LOGGER") as logger:
        app = FastAPI()
        app.middleware("http")(log_request_details)

        @app.post(path)
        async def root():
            return {"message": "Hello World"}

        client = TestClient(app)
        response = client.post(path, content="foo")

        assert response.status_code == 200
        log_level = getattr(logger, level)
        log_level.assert_has_calls(
            [
                call(
                    f"testclient:50000 POST {path}",
                    extra={
                        "request_body": b"foo",
                    },
                ),
                call(
                    f"testclient:50000 POST {path} 200",
                    extra={
                        "request_body": b"foo",
                    },
                ),
            ]
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


@patch("blueapi.service.main.teardown_runner")
@patch("blueapi.service.main.setup_runner")
async def test_lifespan(setup: Mock, teardown: Mock):
    conf = ApplicationConfig()
    lifespan_fn = lifespan(conf)

    app = Mock()

    async with lifespan_fn(app):
        setup.assert_called_once_with(conf)
        teardown.assert_not_called()

    teardown.assert_called_once()

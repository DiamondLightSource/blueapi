import contextlib
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import pytest
from fastapi import FastAPI, Request, WebSocket
from fastapi.testclient import TestClient

from blueapi import __version__
from blueapi.config import ApplicationConfig
from blueapi.service import interface
from blueapi.service.main import (
    get_passthrough_headers,
    lifespan,
    log_request_details,
    run_plan,
)
from blueapi.service.middleware import VersionHeaders
from blueapi.service.runner import WorkerDispatcher


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


@pytest.fixture
def logging_server():
    app = FastAPI()
    app.middleware("http")(log_request_details)

    @app.post("/")
    async def root():
        return {"message": "Hello World"}

    @app.get("/healthz")
    async def health():
        return {"health": "good"}

    return TestClient(app)


async def test_post_request_logs_at_info(logging_server: TestClient):
    with mock.patch("blueapi.service.main.LOGGER") as logger:
        response = logging_server.post("/", content="foo")

        assert response.status_code == 200
        logger.info.assert_has_calls(
            [
                call(
                    "testclient:50000 POST /",
                    extra={
                        "request_body": b"foo",
                    },
                ),
                call(
                    "testclient:50000 POST / 200",
                    extra={
                        "request_body": b"foo",
                    },
                ),
            ]
        )


async def test_get_request_logs_at_debug(logging_server: TestClient):
    with mock.patch("blueapi.service.main.LOGGER") as logger:
        response = logging_server.get("/healthz")

        assert response.status_code == 200
        logger.debug.assert_has_calls(
            [
                call(
                    "testclient:50000 GET /healthz 200",
                    extra={"request_body": b""},
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


async def test_websocket_run_plan():
    ws = Mock(spec=WebSocket)
    runner = Mock(spec=WorkerDispatcher)
    events = MagicMock()
    events.__aiter__.return_value = MagicMock(__anext__=Mock(side_effect=[1, 2, 3]))
    runner.event_pipe.return_value = contextlib.nullcontext(events)
    runner.run.side_effect = lambda mth, *a, **kw: {
        interface.submit_task: "task_uid"
    }.get(mth)

    ws.receive_text = AsyncMock(
        return_value="""{
            "kind": "submit",
            "task": {"name": "foo", "params": {}, "instrument_session": "cm12345-1"}
            }"""
    )

    await run_plan(ws, runner, user="abc12345")
    ws.close.assert_called_once_with()

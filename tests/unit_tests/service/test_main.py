import sys
import types
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from blueapi.service.main import log_request_details, start


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


@pytest.fixture
def mock_config():
    class DummyUrl:
        host = "127.0.0.1"
        port = 8000

    class DummyApi:
        url = DummyUrl
        cors = ""

    class DummyConfig:
        api = DummyApi()
        oidc = None

    return DummyConfig()


def test_start_runs_uvicorn(monkeypatch, mock_config):
    mock_uvicorn_run = mock.Mock()
    mock_instrumentor = mock.Mock()
    mock_get_tracer_provider = mock.Mock()
    monkeypatch.setitem(
        sys.modules, "uvicorn", types.SimpleNamespace(run=mock_uvicorn_run)
    )
    monkeypatch.setitem(
        sys.modules,
        "uvicorn.config",
        types.SimpleNamespace(
            LOGGING_CONFIG={
                "formatters": {"default": {"fmt": ""}, "access": {"fmt": ""}}
            }
        ),
    )
    monkeypatch.setattr(
        "blueapi.service.main.FastAPIInstrumentor", lambda: mock_instrumentor
    )
    monkeypatch.setattr(
        "blueapi.service.main.get_tracer_provider", mock_get_tracer_provider
    )

    start(mock_config)

    assert mock_uvicorn_run.called
    assert mock_instrumentor.instrument_app.called


@pytest.mark.parametrize(
    "missing_attr",
    ["host", "port"],
)
def test_start_raises_if_host_or_port_missing(monkeypatch, mock_config, missing_attr):
    setattr(mock_config.api.url, missing_attr, None)
    monkeypatch.setitem(sys.modules, "uvicorn", types.SimpleNamespace(run=mock.Mock()))
    monkeypatch.setitem(
        sys.modules,
        "uvicorn.config",
        types.SimpleNamespace(
            LOGGING_CONFIG={
                "formatters": {"default": {"fmt": ""}, "access": {"fmt": ""}}
            }
        ),
    )
    monkeypatch.setattr("blueapi.service.main.FastAPIInstrumentor", lambda: mock.Mock())
    monkeypatch.setattr("blueapi.service.main.get_tracer_provider", mock.Mock())
    with pytest.raises(AssertionError, match="api url is missing host or port"):
        start(mock_config)

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from starlette.types import ASGIApp

from blueapi.config import ApplicationConfig
from blueapi.service.middleware import (
    API_VERSION,
    CONTEXT_HEADER,
    VENDOR_CONTEXT_HEADER,
    VERSION,
    ObservabilityContextPropagator,
    VersionHeaders,
)


@pytest.fixture
def app():
    return AsyncMock(spec=ASGIApp)


@pytest.mark.parametrize(
    "protocol,message_type",
    [("http", "http.response.start"), ("websocket", "websocket.accept")],
)
async def test_version_headers_added(app: Mock, protocol: str, message_type: str):
    vh = VersionHeaders(app)

    send = AsyncMock()
    scope = {"type": protocol}
    await vh(scope, Mock(), send)

    # the middleware wraps the send function so we need to extract the function
    # the app was actually called with
    local_send = app.call_args[0][2]

    # Calling the wrapped send method here is equivalent to what the downstream
    # framework would do after the middleware has done its thing
    message = {"type": message_type, "headers": []}
    await local_send(message)

    # Check the headers were sent to the original send method
    send.assert_called_once_with(
        {"type": message_type, "headers": [VERSION, API_VERSION]}
    )


async def test_version_headers_ignore_non_http_or_websockets(app: Mock):
    vh = VersionHeaders(app)

    scope = {"type": "other"}
    send = Mock()
    recv = Mock()

    await vh(scope, recv, send)

    # for non-http/ws requests, the original args are passed directly
    app.assert_called_once_with(scope, recv, send)


async def test_obs_context_ignores_non_http_or_websockets(app: Mock):
    ocp = ObservabilityContextPropagator(app)

    scope = MagicMock()
    scope.__getitem__.side_effect = {"type": "other"}.__getitem__

    with patch("blueapi.service.middleware.attach") as att:
        await ocp(scope, Mock(), Mock())

    att.assert_not_called()
    scope.get.assert_not_called()


@pytest.mark.parametrize("protocol", ["http", "websocket"])
async def test_obs_context_passes_context(app: Mock, protocol: str):
    ocp = ObservabilityContextPropagator(app)
    scope = {"type": protocol, "headers": ((CONTEXT_HEADER, b"req_context"),)}

    with patch("blueapi.service.middleware.attach") as att:
        with patch("blueapi.service.middleware.get_global_textmap") as get_global:
            get_global.return_value.extract.side_effect = lambda x: x
            await ocp(scope, Mock(), Mock())

    att.assert_called_once_with({ApplicationConfig.CONTEXT_HEADER: "req_context"})


@pytest.mark.parametrize("protocol", ["http", "websocket"])
async def test_obs_context_passes_vendor_context(app: Mock, protocol: str):
    ocp = ObservabilityContextPropagator(app)
    scope = {
        "type": protocol,
        "headers": (
            (CONTEXT_HEADER, b"req_context"),
            (VENDOR_CONTEXT_HEADER, b"vendor_context"),
        ),
    }

    with patch("blueapi.service.middleware.attach") as att:
        with patch("blueapi.service.middleware.get_global_textmap") as get_global:
            get_global.return_value.extract.side_effect = lambda x: x
            await ocp(scope, Mock(), Mock())

    att.assert_called_once_with(
        {
            ApplicationConfig.CONTEXT_HEADER: "req_context",
            ApplicationConfig.VENDOR_CONTEXT_HEADER: "vendor_context",
        }
    )

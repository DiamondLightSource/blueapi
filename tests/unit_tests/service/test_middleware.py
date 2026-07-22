from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, patch

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
    WebsocketTracing,
    _redact_headers,
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
    scope.get.assert_called_once_with("type")


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


def test_redact_headers():
    assert list(_redact_headers([(b"authorization", b"Bearer foobar")])) == [
        (b"authorization", b"Bearer [REDACTED]")
    ]
    assert list(_redact_headers([(b"other-header", b"Not affected")])) == [
        (b"other-header", b"Not affected")
    ]


@pytest.fixture
def asgi() -> AsyncMock:
    return AsyncMock(name="asgi-app", spec=ASGIApp)


@pytest.fixture
def ws_tracer(asgi: Mock) -> WebsocketTracing:
    return WebsocketTracing(asgi)


@pytest.fixture
def send() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def receive() -> AsyncMock:
    return AsyncMock()


# logger patch that defaults to enabled for all levels
def patch_ws_logger(func):
    return patch(
        "blueapi.service.middleware.WS_LOGGER",
        isEnabledFor=Mock(name="custom", return_value=True),
    )(func)


@patch_ws_logger
async def test_websocket_tracing_does_nothing_when_not_debug(
    log: Mock,
    asgi: AsyncMock,
    ws_tracer: WebsocketTracing,
    send: AsyncMock,
    receive: AsyncMock,
):
    scope = {"type": "websocket"}
    log.isEnabledFor.return_value = False
    await ws_tracer(scope, receive, send)

    asgi.assert_called_once_with(scope, receive, send)


@patch_ws_logger
async def test_websocket_tracing_does_nothing_for_http(
    log: Mock,
    asgi: AsyncMock,
    ws_tracer: WebsocketTracing,
    send: AsyncMock,
    receive: AsyncMock,
):
    scope = {"type": "http"}
    await ws_tracer(scope, receive, send)

    asgi.assert_called_once_with(scope, receive, send)


@patch_ws_logger
async def test_websocket_tracing_logs_new_connection(
    log: Mock, ws_tracer: WebsocketTracing, send: AsyncMock, receive: AsyncMock
):
    scope = {"type": "websocket", "headers": [(b"authorization", b"bearer foobar")]}
    await ws_tracer(scope, receive, send)
    log.debug.assert_called_once_with(
        "New Connection from %r",
        {"type": "websocket", "headers": [(b"authorization", b"bearer [REDACTED]")]},
        extra=ANY,
    )


@pytest.mark.parametrize(
    "type,other,log_args",
    [
        (
            "websocket.send",
            {"text": "demo"},
            ("Sending: %r", "demo"),
        ),
        (
            "websocket.accept",
            {"headers": [(b"bapi-version", b"1.2.3")]},
            (
                "Accepting websocket - sending headers: %r",
                [(b"bapi-version", b"1.2.3")],
            ),
        ),
        (
            "websocket.close",
            {"code": 1234, "reason": "error_code"},
            ("Closing with code: %r, reason: %r", 1234, "error_code"),
        ),
        (
            "websocket.http.response.start",
            {"status": "ws-status", "headers": [(b"bapi-version", b"1.2.3")]},
            (
                "HTTP Response: status=%r, headers=%r",
                "ws-status",
                [(b"bapi-version", b"1.2.3")],
            ),
        ),
        (
            "websocket.http.response.body",
            {"body": "response content"},
            (
                "HTTP Response Content: %r",
                "response content",
            ),
        ),
        (
            "unknown.msg.type",
            {"other": "data"},
            ("Sending other: %r", {"type": "unknown.msg.type", "other": "data"}),
        ),
    ],
)
@patch_ws_logger
async def test_websocket_tracing_local_send(
    log: Mock,
    asgi: AsyncMock,
    ws_tracer: WebsocketTracing,
    send: AsyncMock,
    type: str,
    other: dict[str, Any],
    log_args: tuple[tuple[str, ...], dict[str, Any]],
):
    await ws_tracer({"type": "websocket"}, AsyncMock(), send)

    _, _, local_send = asgi.call_args[0]

    message = {"type": type, **other}
    await local_send(message)
    log.debug.assert_called_with(*log_args, extra=ANY)

    # Original send method should be called with original message
    send.assert_called_once_with(message)


@pytest.mark.parametrize(
    "type,other,log_args",
    [
        (
            "websocket.receive",
            {"text": "demo"},
            ("Received: %r", "demo"),
        ),
        (
            "websocket.connect",
            {},
            ("New connection from %s:%d", "unknown", 0),
        ),
        ("unknown.msg", {}, ("Received other: %r", {"type": "unknown.msg"})),
    ],
)
@patch_ws_logger
async def test_websocket_tracing_local_receive(
    log: Mock,
    asgi: AsyncMock,
    ws_tracer: WebsocketTracing,
    receive: AsyncMock,
    type: str,
    other: dict[str, Any],
    log_args: tuple[tuple[str, ...], dict[str, Any]],
):
    await ws_tracer({"type": "websocket"}, receive, AsyncMock())

    _, local_recv, _ = asgi.call_args[0]

    message = {"type": type, **other}
    receive.return_value = message

    received = await local_recv()

    # original receive called to get message
    receive.assert_called_once_with()

    log.debug.assert_called_with(*log_args, extra=ANY)

    # We should not be modifying anything
    assert received == message

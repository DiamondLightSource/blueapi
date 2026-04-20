import logging
import uuid

from opentelemetry.context import attach
from opentelemetry.propagate import get_global_textmap
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from blueapi import __version__
from blueapi.config import ApplicationConfig

OBS_LOGGER = logging.getLogger("blueapi.service.middleware.observability")
WS_LOGGER = logging.getLogger("blueapi.service.middleware.websocket")

CONTEXT_HEADER = ApplicationConfig.CONTEXT_HEADER.encode()
VENDOR_CONTEXT_HEADER = ApplicationConfig.VENDOR_CONTEXT_HEADER.encode()

API_VERSION = (b"x-api-version", ApplicationConfig.REST_API_VERSION.encode("utf-8"))
VERSION = (b"x-blueapi-version", __version__.encode("utf-8"))


class VersionHeaders:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope.get("type") not in ("websocket", "http"):
            return await self.app(scope, receive, send)

        async def local_send(message: Message):
            if message["type"] in ("websocket.accept", "http.response.start"):
                message["headers"].append(VERSION)
                message["headers"].append(API_VERSION)
            await send(message)

        return await self.app(scope, receive, local_send)


class ObservabilityContextPropagator:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope.get("type") not in ("http", "websocket"):
            return await self.app(scope, receive, send)

        ctx = None
        v_ctx = None
        for key, val in scope.get("headers", ()):
            if key == CONTEXT_HEADER:
                ctx = val.decode()
            elif key == VENDOR_CONTEXT_HEADER:
                v_ctx = val.decode()
        if ctx:
            OBS_LOGGER.debug("Propagating observability context: %s, %s", ctx, v_ctx)
            carrier = {ApplicationConfig.CONTEXT_HEADER: ctx}
            if v_ctx:
                carrier[ApplicationConfig.VENDOR_CONTEXT_HEADER] = v_ctx
            attach(get_global_textmap().extract(carrier))

        return await self.app(scope, receive, send)


class WebsocketTracing:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        active = WS_LOGGER.isEnabledFor(logging.DEBUG)

        if scope.get("type") != "websocket" or not active:
            return await self.app(scope, receive, send)

        conn_id = uuid.uuid4()
        client: tuple[str, int] = scope.get("client", ("unknown", 0))
        extra = {"conn": conn_id, "client": client}

        WS_LOGGER.debug("%r", scope, extra=extra)

        async def local_send(msg: Message):
            match msg.get("type"):
                case "websocket.send":
                    WS_LOGGER.debug("Sending: %r", msg.get("text"), extra=extra)
                case "websocket.accept":
                    WS_LOGGER.debug(
                        "Accepting websocket - sending headers: %r",
                        msg.get("headers"),
                        extra=extra,
                    )
                case "websocket.close":
                    WS_LOGGER.debug(
                        "Closing with code: %r, reason: %r",
                        msg.get("code"),
                        msg.get("reason"),
                        extra=extra,
                    )
                case "websocket.http.response.start":
                    WS_LOGGER.debug(
                        "HTTP Response: status=%r, headers=%r",
                        msg.get("status"),
                        msg.get("headers"),
                        extra=extra,
                    )
                case "websocket.http.response.body":
                    WS_LOGGER.debug(
                        "HTTP Response Content: %r", msg.get("body"), extra=extra
                    )
                case _:
                    WS_LOGGER.debug("Sending other: %r", msg, extra=extra)

            await send(msg)

        async def local_receive() -> Message:
            message = await receive()
            WS_LOGGER.debug("Received: %r", message)
            return message

        return await self.app(scope, local_receive, local_send)

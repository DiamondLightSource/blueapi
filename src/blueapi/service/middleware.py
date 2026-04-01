import logging

from opentelemetry.context import attach
from opentelemetry.propagate import get_global_textmap
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from blueapi import __version__
from blueapi.config import ApplicationConfig

OBS_LOGGER = logging.getLogger("blueapi.service.middleware.observability")

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

        await self.app(scope, receive, local_send)


class ObservabilityContextPropagator:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] not in ("http", "websocket"):
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

        await self.app(scope, receive, send)

import logging
import re
import uuid
from collections.abc import Iterable, Sequence

from fastapi.datastructures import Headers
from fastapi.responses import PlainTextResponse
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


Header = tuple[bytes, bytes]


def _redact_headers(headers: list[Header] | None) -> Iterable[Header]:
    for key, value in headers or []:
        if key == b"authorization":
            if (space := value.find(b" ")) >= 0:
                value = value[:space] + b" [REDACTED]"
        yield (key, value)


class WebsocketOriginCheck:
    def __init__(
        self,
        app: ASGIApp,
        allow_origins: Sequence[str] = (),
        allow_origin_regex: str | None = None,
    ):
        self.app = app
        if "*" == allow_origins or (
            "*" in allow_origins and not isinstance(allow_origins, str)
        ):
            # a single str is also a Sequence[str] and '*.example.com' should
            # not count as a full wildcard
            self.allow_origins = None
        elif isinstance(allow_origins, str):
            self.allow_origins = {allow_origins}
        else:
            self.allow_origins = set(allow_origins)

        self.allow_origin_regex = (
            re.compile(allow_origin_regex) if allow_origin_regex else None
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope.get("type") != "websocket" or (
            # we're not going to check the origin anyway
            self.allow_origins is None and self.allow_origin_regex is None
        ):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        origin = headers.get("origin")

        if origin is not None and not self.allow_origin(origin):
            response = PlainTextResponse("Origin not on allow list", 403)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    def allow_origin(self, origin: str) -> bool:
        allow = self.allow_origins is not None and origin in self.allow_origins
        if not allow and self.allow_origin_regex is not None:
            allow = self.allow_origin_regex.match(origin) is not None
        return allow


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

        WS_LOGGER.debug(
            "New Connection from %r",
            {**scope, "headers": list(_redact_headers(scope.get("headers")))},
            extra=extra,
        )

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
            match message.get("type"):
                case "websocket.receive":
                    WS_LOGGER.debug("Received: %r", message.get("text"), extra=extra)
                case "websocket.connect":
                    WS_LOGGER.debug("New connection from %s:%d", *client, extra=extra)
                case _:
                    WS_LOGGER.debug("Received other: %r", message, extra=extra)
            return message

        return await self.app(scope, local_receive, local_send)

import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

import jwt
from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.datastructures import Address
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from observability_utils.tracing import start_as_current_span
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.trace import get_tracer_provider
from starlette.responses import JSONResponse

from blueapi.config import ApplicationConfig
from blueapi.service.authentication import build_access_token_check
from blueapi.service.middleware import (
    ObservabilityContextPropagator,
    VersionHeaders,
    WebsocketOriginCheck,
    WebsocketTracing,
)

from .authorization import OpaClient, validate_tiled_config
from .routes import devices, environment, meta, plans, run_plan, tasks, worker
from .routes.dependencies import TRACER, setup_runner, teardown_runner

LOGGER = logging.getLogger(__name__)

# Routers served under /api/v1 and, deprecated, at the root
SECURE_ROUTERS = (
    environment.router,
    plans.router,
    devices.router,
    tasks.router,
    worker.router,
    meta.router,
)


def lifespan(config: ApplicationConfig):
    @asynccontextmanager
    async def inner(app: FastAPI):
        metadata = config.env.metadata
        setup_runner(config)
        async with OpaClient.for_config(
            metadata and metadata.instrument, config.opa
        ) as opa:
            app.state.authz = opa
            await validate_tiled_config(config.tiled.authentication, config.oidc, opa)
            yield
        teardown_runner()

    return inner


def get_app(config: ApplicationConfig):
    app = FastAPI(
        docs_url=ApplicationConfig.DOCS_ENDPOINT,
        title="BlueAPI Control",
        summary="BlueAPI wraps bluesky plans and devices and "
        "exposes endpoints to send commands/receive data",
        lifespan=lifespan(config),
        version=ApplicationConfig.REST_API_VERSION,
        license_info=ApplicationConfig.LICENSE_INFO,
        openapi_tags=ApplicationConfig.TAG_METADATA,
    )
    dependencies = []
    if config.oidc:
        dependencies.append(Depends(build_access_token_check(config.oidc)))
        app.swagger_ui_init_oauth = {
            "clientId": "NOT_SUPPORTED",
        }
    app.include_router(meta.open_router)
    for router in SECURE_ROUTERS:
        app.include_router(router, prefix="/api/v1", dependencies=dependencies)
    app.include_router(run_plan.router, prefix="/api/v2", dependencies=dependencies)
    for router in SECURE_ROUTERS:
        app.include_router(router, deprecated=True, dependencies=dependencies)
    app.add_exception_handler(KeyError, on_key_error_404)
    app.add_exception_handler(jwt.PyJWTError, on_token_error_401)

    app.add_middleware(ObservabilityContextPropagator)
    app.add_middleware(VersionHeaders)
    app.add_middleware(WebsocketTracing)
    app.middleware("http")(log_request_details)
    if config.api.cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.api.cors.origins,
            allow_credentials=config.api.cors.allow_credentials,
            allow_methods=config.api.cors.allow_methods,
            allow_headers=config.api.cors.allow_headers,
        )
        app.add_middleware(
            WebsocketOriginCheck,
            allow_origins=config.api.cors.origins,
        )
    return app


async def on_key_error_404(_: Request, __: Exception):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "Item not found"},
    )


async def on_token_error_401(_: Request, __: Exception):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Not authenticated"},
        headers={"WWW-Authenticate": "Bearer"},
    )


@start_as_current_span(TRACER, "config")
def start(config: ApplicationConfig):
    import uvicorn
    from uvicorn.config import LOGGING_CONFIG

    # Enable propagation and disable default handlers, so that blueapi handles all logs
    LOGGING_CONFIG["loggers"]["uvicorn"]["handlers"] = []
    LOGGING_CONFIG["formatters"]["access"]["fmt"] = (
        "%(asctime)s %(levelprefix)s %(client_addr)s"
        + " - '%(request_line)s' %(status_code)s"
    )
    LOGGING_CONFIG["loggers"]["uvicorn"]["propagate"] = True
    app = get_app(config)

    FastAPIInstrumentor().instrument_app(
        app,
        tracer_provider=get_tracer_provider(),
        http_capture_headers_server_request=[",*"],
        http_capture_headers_server_response=[",*"],
    )
    app.state.config = config
    assert config.api.url.host is not None, "API URL missing host"
    assert config.api.url.port is not None, "API URL missing port"
    uvicorn.run(
        app, host=config.api.url.host, port=config.api.url.port, access_log=False
    )


async def log_request_details(
    request: Request, call_next: Callable[[Request], Awaitable[StreamingResponse]]
) -> Response:
    """Middleware to log request's host, method, path, status and request and
    body

    Logs GET as debug, all else as info."""
    log = LOGGER.debug if request.method == "GET" else LOGGER.info
    request_body = await request.body()
    client = request.client or Address("Unknown", -1)
    log_message = f"{client.host}:{client.port} {request.method} {request.url.path}"
    extra = {
        "request_body": request_body,
    }
    if request.method != "GET":
        log(log_message, extra=extra)

    response = await call_next(request)
    log_message += f" {response.status_code}"
    log(log_message, extra=extra)

    return response

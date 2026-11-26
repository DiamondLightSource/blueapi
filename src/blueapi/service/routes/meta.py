import urllib.parse

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from observability_utils.tracing import start_as_current_span

from blueapi.config import ApplicationConfig, OIDCConfig, Tag
from blueapi.service import interface
from blueapi.service.model import Health, HealthProbeResponse

from .dependencies import TRACER, Runner

open_router = APIRouter()
router = APIRouter()


@open_router.get("/", include_in_schema=False)
def root_redirect() -> RedirectResponse:
    """Redirect to docs url"""
    return RedirectResponse(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        url=ApplicationConfig.DOCS_ENDPOINT,
    )


@open_router.get(
    "/config/oidc",
    tags=[Tag.META],
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "No Authentication configured"}
    },
)
@start_as_current_span(TRACER)
def get_oidc_config(runner: Runner) -> OIDCConfig:
    """Retrieve the OpenID Connect (OIDC) configuration for the server."""
    config = runner.run(interface.get_oidc_config)
    if config is None:
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT)
    return config


@open_router.get("/healthz", status_code=status.HTTP_200_OK, tags=[Tag.META])
def health_probe() -> HealthProbeResponse:
    """If able to serve this, server is live and ready for requests."""
    return HealthProbeResponse(status=Health.OK)


@router.get("/logout", include_in_schema=False)
def logout(runner: Runner) -> Response:
    """Redirect to logout url"""
    config = runner.run(interface.get_oidc_config)
    if config is None or not config.logout_redirect_endpoint:
        raise HTTPException(status_code=status.HTTP_205_RESET_CONTENT)

    encoded_url = urllib.parse.quote_plus(config.end_session_endpoint)
    return RedirectResponse(
        status_code=status.HTTP_308_PERMANENT_REDIRECT,
        url=config.logout_redirect_endpoint.rstrip("/") + "?rd=" + encoded_url,
    )

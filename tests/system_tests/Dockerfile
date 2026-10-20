# Runtime image plus dodal (demo extra) for system tests, keeps dodal out of the published image
ARG BASE_IMAGE=ghcr.io/diamondlightsource/blueapi:latest
FROM ${BASE_IMAGE}

# The base image ships the blueapi source and uv.lock, so install the locked demo extra into its venv
WORKDIR /workspaces/blueapi
RUN UV_PROJECT_ENVIRONMENT=/app/.venv uv sync --locked --no-dev --no-editable --inexact --extra demo

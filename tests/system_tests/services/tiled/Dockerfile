# Local stand-in for ghcr.io/diamondlightsource/dls-tiled until it is released
# against tiled 0.2.20: the upstream tiled image with the Diamond access policy
# (dls_tiled/policy.py, ported to the 0.2.20 access_tags model) added to its venv.
ARG TILED_VERSION=0.2.20

FROM ghcr.io/bluesky/tiled:${TILED_VERSION}
ARG TILED_VERSION

COPY dls_tiled /deploy/plugins/dls_tiled
ENV PYTHONPATH=/deploy/plugins

# Check the policy imports and that upstream tiled was left at its release
RUN python -c "import dls_tiled.policy, tiled; \
assert tiled.__version__ == '${TILED_VERSION}', tiled.__version__"

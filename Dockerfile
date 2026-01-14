# The devcontainer should use the developer target and run as root with podman
# or docker with user namespaces.
FROM ghcr.io/diamondlightsource/ubuntu-devcontainer:noble AS developer

# Add any system dependencies for the developer/build environment here
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    graphviz \
    && apt-get dist-clean

# Install helm for the dev container. This is the recommended 
# approach per the docs: https://helm.sh/docs/intro/install
RUN curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3; \
    chmod 700 get_helm.sh; \
    ./get_helm.sh; \
    rm get_helm.sh
RUN helm plugin install https://github.com/losisin/helm-values-schema-json.git --version 2.3.1

# The build stage installs the context into the venv
FROM developer AS build

# Change the working directory to the `app` directory
# and copy in the project
WORKDIR /app
COPY . /app
RUN chmod o+wrX .

# Tell uv sync to install python in a known location so we can copy it out later
ENV UV_PYTHON_INSTALL_DIR=/python

RUN uv add debugpy

# Sync the project without its dev dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable --no-dev

# The runtime stage copies the built venv into a runtime container
FROM ubuntu:noble AS runtime

# Add apt-get system dependecies for runtime here if needed
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    # Git required for installing packages at runtime
    git \
    # gdb required for attaching debugger
    gdb \
    # May be required if attaching devcontainer
    libnss-ldapd \
    && apt-get dist-clean

# Install uv to allow setup-scratch to run
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

# For this pod to understand finding user information from LDAP
RUN sed -i 's/files/ldap files/g' /etc/nsswitch.conf

# Set the MPLCONFIGDIR environment variable to a temporary directory to avoid
# writing to the home directory. This is necessary because the home directory
# is read-only in the runtime container.
# https://matplotlib.org/stable/install/environment_variables_faq.html#envvar-MPLCONFIGDIR

ENV MPLCONFIGDIR=/tmp/matplotlib

# Copy the python installation from the build stage
COPY --from=build /python /python

# Copy the environment, but not the source code
COPY --chown=1000:1000 --from=build /app/.venv /app/.venv
RUN chmod o+wrX /app/.venv
ENV PATH=/app/.venv/bin:$PATH

# Add copy of blueapi source to container for debugging
WORKDIR /workspaces
COPY --chown=1000:1000 . blueapi
# Make allowance for non-1000 uid
RUN chmod o+wrX blueapi

# Make invariant symlink to site-packages for debugging
# /app/.venv/lib/python/site-packages/blueapi:/workspaces/blueapi
WORKDIR /app/.venv/lib
RUN ln -s python* python

# Switch user 1000
USER ubuntu

ENTRYPOINT ["blueapi"]
CMD ["serve"]

# The devcontainer should use the developer target and run as root with podman
# or docker with user namespaces.
# Version SHA has been removed, see: https://github.com/DiamondLightSource/blueapi/issues/1053
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION} AS developer

# Add any system dependencies for the developer/build environment here
RUN apt-get update && apt-get install -y --no-install-recommends \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

# Install helm for the dev container. This is the recommended 
# approach per the docs: https://helm.sh/docs/intro/install
RUN curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3; \
    chmod 700 get_helm.sh; \
    ./get_helm.sh; \
    rm get_helm.sh
RUN helm plugin install https://github.com/losisin/helm-values-schema-json.git --version 2.2.1

# Set up a virtual environment and put it in PATH
RUN python -m venv /venv
ENV PATH=/venv/bin:$PATH

# The build stage installs the context into the venv
FROM developer AS build
RUN mkdir -p /.cache/pip; chmod o+wrX /.cache/pip
# Requires buildkit 0.17.0
COPY --chmod=o+wrX . /workspaces/blueapi
WORKDIR /workspaces/blueapi
RUN touch dev-requirements.txt && pip install --upgrade pip && pip install debugpy && pip install -c dev-requirements.txt .

# The runtime stage copies the built venv into a slim runtime container
FROM python:${PYTHON_VERSION}-slim AS runtime
# Add apt-get system dependecies for runtime here if needed
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    # Git required for installing packages at runtime
    git \
    # gdb required for attaching debugger
    gdb \
    # May be required if attaching devcontainer
    libnss-ldapd \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build --chmod=o+wrX /venv/ /venv/
COPY --from=build --chmod=o+wrX /.cache/pip /.cache/pip

ENV PATH=/venv/bin:$PATH
ENV PYTHONPYCACHEPREFIX=/tmp/blueapi_pycache

# For this pod to understand finding user information from LDAP
RUN sed -i 's/files/ldap files/g' /etc/nsswitch.conf

# Set the MPLCONFIGDIR environment variable to a temporary directory to avoid
# writing to the home directory. This is necessary because the home directory
# is read-only in the runtime container.
# https://matplotlib.org/stable/install/environment_variables_faq.html#envvar-MPLCONFIGDIR

ENV MPLCONFIGDIR=/tmp/matplotlib

# Make a path to site-packages that is invariant with python version
# This allows our pathMapping in launch.jsons to always find build blueapi
WORKDIR /venv/lib
RUN ln -s python python${PYTHON_VERSION}

RUN groupadd -g 1000 blueapi && \
    useradd -m -u 1000 -g blueapi blueapi

# Switch to the custom user
USER blueapi

ENTRYPOINT ["blueapi"]
CMD ["serve"]

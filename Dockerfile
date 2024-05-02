# The devcontainer should use the developer target and run as root with podman
# or docker with user namespaces.
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION} as developer

# Add any system dependencies for the developer/build environment here
RUN apt-get update && apt-get install -y --no-install-recommends \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

# Set up a virtual environment and put it in PATH
RUN python -m venv /venv
ENV PATH=/venv/bin:$PATH

# The build stage installs the context into the venv
FROM developer as build
COPY . /context
WORKDIR /context
RUN pip install .

# The runtime stage copies the built venv into a slim runtime container
FROM python:${PYTHON_VERSION}-slim as runtime
# Add apt-get system dependecies for runtime here if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Git required for installing packages at runtime
    git \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /venv/ /venv/
COPY ./container-startup.sh /container-startup.sh
ENV PATH=/venv/bin:$PATH


RUN mkdir -p /.cache/pip; chmod -R 777 /venv /.cache/pip

# change this entrypoint if it is not the same as the repo
ENTRYPOINT ["/container-startup.sh"]
CMD ["serve"]

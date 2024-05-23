# Run in a container

Pre-built containers with blueapi and its dependencies already
installed are available on `Github Container Registry
<https://ghcr.io/DiamondLightSource/blueapi>`_.

## Starting the container

To pull the container from github container registry and run::

    `docker run ghcr.io/diamondlightsource/blueapi:main --version`

with `podman`:

    `podman run ghcr.io/diamondlightsource/blueapi:main --version`

To get a released version, use a numbered release instead of `main`.

# Run in a Container

Pre-built containers with blueapi and its dependencies already
installed are available on `GitHub Container Registry
<https://ghcr.io/DiamondLightSource/blueapi>`_.

## Starting the container

To pull the container from GitHub container registry and run::

```
docker run ghcr.io/diamondlightsource/blueapi:latest
```

with `podman`:

```
podman run ghcr.io/diamondlightsource/blueapi:latest
```

To get a released version, use a numbered release instead of `latest`.

## Starting the RabbitMQ
The worker requires a running instance of RabbitMQ. The easiest way to start it is
 to `compose` the services in `tests/system_tests/compose.yaml`

```sh
docker compose -f tests/system_tests/compose.yaml run rabbitmq --detach
```

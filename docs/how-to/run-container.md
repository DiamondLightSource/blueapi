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

## Starting the message bus

The worker requires a running instance of the message bus, which in this case is RabbitMQ. The easiest way to start it
along with the other services is `just services`, or to run RabbitMQ on its own with the STOMP plugin enabled:

```sh
docker run --detach -p 61613:61613 --security-opt label=disable \
    -v ./tests/system_tests/services/rabbitmq_plugins:/etc/rabbitmq/enabled_plugins \
    docker.io/rabbitmq:4.0-management
```

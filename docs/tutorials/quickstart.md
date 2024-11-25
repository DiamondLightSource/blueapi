# Quickstart Guide

Blueapi acts as a worker that can run bluesky plans against devices for a specific
laboratory setup. It can control devices to collect data and export events to tell
downstream services about the data it has collected.

## Start Services

The worker requires other infrastructure services running- these are captured in a [compose-spec](https://github.com/compose-spec/compose-spec/blob/main/spec.md) file: `.devcontainer/compose.yml`, and may later be started as part of building the devcontainer when [compatibility with podman is improved](https://github.com/devcontainers/cli/issues/863).

To run the services:
```
    # with docker
    docker compose -f .devcontainer/compose.yml up
    # or with podman-compose
    podman-compose -f .devcontainer/compose.yml up
```

This creates and configures:
- RabbitMQ with the rabbitmq_stomp plugin exposed at localhost:61613

## Start Worker

To start the worker:

```
    blueapi serve
```

The worker can also be started with additional configuration from file:

```
    blueapi --config path/to/file serve
    # or
    blueapi -c path/to/file serve
```

A config file compatible with the services in the compose-spec above is included alongside it:

```
    .devcontainer/config.yml
```

## Test that the Worker is Running

Blueapi comes with a CLI so that you can query and control the worker from the terminal, this should be passed the same config as the worker:

```
    blueapi [--config path/to/file] controller plans
```

The above command should display all plans the worker is capable of running.



See also [full cli reference](../reference/cli.md)

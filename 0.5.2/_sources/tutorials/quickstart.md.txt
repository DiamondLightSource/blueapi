# Quickstart Guide

Blueapi acts as a worker that can run bluesky plans against devices for a specific
laboratory setup. It can control devices to collect data and export events to tell
downstream services about the data it has collected.

## Start ActiveMQ

The worker requires a running instance of ActiveMQ, the simplest
way to start it is to run it via a container:

```
    docker run -it --rm --net host rmohr/activemq:5.15.9-alpine
```

```
    podman run -it --rm --net host rmohr/activemq:5.15.9-alpine
```

## Start Worker

To start the worker:

```
    blueapi serve
```

The worker can also be started using a custom config file:

```
    blueapi --config path/to/file serve
```

## Test that the Worker is Running

Blueapi comes with a CLI so that you can query and control the worker from the terminal.

```
    blueapi controller plans
```

The above command should display all plans the worker is capable of running.

See also [full cli reference](../reference/cli.md)

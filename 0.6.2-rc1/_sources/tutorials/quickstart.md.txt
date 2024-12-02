# Quickstart guide

Blueapi acts as a worker that can run bluesky plans against devices for a specific
laboratory setup. It can control devices to collect data and export events to tell
downstream services about the data it has collected.

## Start Worker

To start the worker:

```
blueapi serve
```

The worker can also be started using a custom config file:

```
blueapi --config path/to/file serve
```

An example of a config file that starts STOMP with default values can be found in:

```
    src/script/stomp_config.yml
```

## Test that the Worker is Running

Blueapi comes with a CLI so that you can query and control the worker from the terminal.

```
blueapi controller plans
```

The above command should display all plans the worker is capable of running.



See also [full cli reference](../reference/cli.md)

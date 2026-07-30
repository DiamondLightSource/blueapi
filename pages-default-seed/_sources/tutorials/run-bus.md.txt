# Run with local message bus

Blueapi can publish updates to a message bus asynchronously, the CLI can then view these updates display them to the user.

## Start RabbitMQ

The worker requires a running instance of RabbitMQ. The easiest way to start it is
 to `compose` the services in `tests/system_tests/compose.yaml`

```sh
docker compose -f tests/system_tests/compose.yaml run rabbitmq --detach
```

## Config File

Create a YAML file for configuring blueapi:

```{literalinclude} ../../tests/unit_tests/valid_example_config/stomp.yaml
:language: yaml
```

## Run the Server

```
blueapi --config /path/to/stomp.yaml serve
```

The server should print a connection message to the console. If there is an error, it will print an error message instead.

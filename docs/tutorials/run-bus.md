# Run with local message bus

Blueapi can publish updates to a message bus asynchronously, the CLI can then view these updates display them to the user.

## Start RabbitMQ

The worker requires a running instance of RabbitMQ. The easiest way to start it is
 to `compose` the services in `tests/system_tests/compose.yaml`

```sh
docker compose -f tests/system_tests/compose.yaml run rabbitmq --detach
```
For those who use `pip install blueapi`, run:

```sh
echo "[rabbitmq_stomp].">enabled_plugins && podman run -it --rm --name rabbitmq-docs -v $(readlink -f enabled_plugins):/etc/rabbitmq/enabled_plugins:z -p 5672:5672 -p 61613:61613 rabbitmq:latest
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

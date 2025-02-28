# Run with local message bus

Blueapi can publish updates to a message bus asynchronously, the CLI can then view these updates display them to the user.

## Start RabbitMQ

The worker requires a running instance of RabbitMQ. The easiest way to start it is
 to execute the provided script:

```
    src/script/start_rabbitmq.sh
```

## Config File

Create a YAML file for configuring blueapi:

```yaml
# stomp.yaml

# Edit this if your message bus of choice is running on a different host, 
# if it has different credentials, 
# or if its STOMP plugin is running on a different port
stomp:
    host: localhost
    port: 61613
    auth:
        username: guest
        # This is for local development only, production systems should use good passwords
        password: guest
```

## Run the Server

```
blueapi --config stomp.yaml serve
```

It should print a message about being connected to the console, otherwise it will print an error.

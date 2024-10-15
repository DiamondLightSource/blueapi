# Run with Local Message Bus

Blueapi can publish updates to a message bus asynchronously, the CLI can then view these updates display them to the user.

## Start Message Bus

The worker requires a running instance of a message bus such as  ActiveMQ, the simplest
way to start it is to run it via a container:

```
    docker run -it --rm --net host rmohr/activemq:5.15.9-alpine
```

```
    podman run -it --rm --net host rmohr/activemq:5.15.9-alpine
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

## Run the CLI

```
blueapi --config stomp.yaml controller run scan '{"detectors": ["image_det"], spec: {"type": "Line", "axis": "x", "start": 0, "stop": 10, "num": 10}}'
```

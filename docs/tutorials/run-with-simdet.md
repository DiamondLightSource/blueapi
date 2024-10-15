# Run with a Simulated AreaDetector

Blueapi can ingest custom devices for use in plans. For example, a simulated EPICS AreaDetector.

## Run a Simulated AreaDetector

First you will need a simulated AreaDetector running on your workstation. [This tutorial] provides an easy way to set one up using docker/podman.

## Config File

> **_NOTE:_** Assumes you have followed [Run with Local Message Bus](./run-with-bus.md).

Create a config file for blueapi:

```yaml
# adsim.yaml

env:
    sources:
        # Imports the ophyd-async devices for controlling the simulated AreaDetector.
        # If interested, the code can be found here: 
        - kind: dodal
          module: dodal.beamlines.adsim

        # Imports the default set of plans into blueapi (scan, count, move, etc.) 
        - kind: planFunctions
          module: dls_bluesky_core.plans
        - kind: planFunctions
          module: dls_bluesky_core.stubs

stomp:
    host: localhost
    port: 61613
    auth:
        username: guest
        password: guest
```

## Run the Server

```
    blueapi --config adsim.yaml serve
```

## Run the CLI

```
# View devices
blueapi --config adsim.yaml controller devices

# Run a scan
blueapi --config adsim.yaml controller run scan '{"detectors": ["adsim"], spec: {"type": "Line", "axis": "x", "start": 0, "stop": 10, "num": 10}}'
```

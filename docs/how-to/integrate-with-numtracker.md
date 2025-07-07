# Integrate With Numtracker

[Numtracker](https://github.com/DiamondLightSource/numtracker.git) is a DLS API that can be used to coordinate where detectors write their data.

## Prequisities

You will need to [get numtracker itself configured for your instrument](https://github.com/DiamondLightSource/numtracker/wiki/new_beamline). 

Blueapi needs [valid authentication configured](./authenticate.md) to communicate with numtracker. It will propogate its auth token so both blueapi and numtracker should be aware of who the user is and that they have permission to be on the instrument sessions (visits) that are intended for use.

## Configuration

Numtracker integration requires the following configuration for blueapi:

```yaml
# If using helm values all of the following goes under worker:

numtracker:
  url: https://numtracker.diamond.ac.uk/graphql
env:
  metadata:
    instrument: <name of your instrument, e.g. i22>
```

Numtracker will work for any ophyd-async [`StandardDetector`](https://blueskyproject.io/ophyd-async/main/_api/ophyd_async/ophyd_async.core.html#ophyd_async.core.StandardDetector)(s) in your project.

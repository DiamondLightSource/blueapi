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

For a more complete example see the [p46 helm chart configuration](https://github.com/epics-containers/p46-services/blob/main/services/p46-blueapi/values.yaml).

Numtracker will work for any ophyd-async [`StandardDetector`](https://blueskyproject.io/ophyd-async/main/_api/ophyd_async/ophyd_async.core.html#ophyd_async.core.StandardDetector)(s) in your project.

## Updating Blueapi and Dodal

Blueapi uses an internal [`PathProvider`](https://blueskyproject.io/ophyd-async/main/_api/ophyd_async/ophyd_async.core.html#ophyd_async.core.PathProvider) when integrated with numtracker, it does not support custom providers in from dodal modules, if your beamline definition in dodal is prefixed with something like this, it should be removed before attempting to use numtracker:

```python
# Currently we must hard-code the visit, determining the visit at runtime requires
# infrastructure that is still WIP.
# Communication with GDA is also WIP so for now we determine an arbitrary scan number
# locally and write the commissioning directory. The scan number is not guaranteed to
# be unique and the data is at risk - this configuration is for testing only.
set_path_provider(
    StaticVisitPathProvider(
        BL,
        Path("/dls/i22/data/2024/cm37271-2/bluesky"),
        client=RemoteDirectoryServiceClient("http://i22-control:8088/api"),
    )
)
```

Numtracker should work with out-of-box plans that take data via runs. Opening a new run will make the `RunEngine` call numtracker and request a fresh data area. Some plans from before numtracker have a decorator that coordinates where detectors write their data: [`@attach_data_session_metadata_decorator`](https://github.com/DiamondLightSource/dodal/blob/10a9a124931901d7666659c6dbe77215d22a8bfd/src/dodal/plan_stubs/data_session.py#L60). This decorator becomes a no-op with numtracker and can be safely removed from plans.

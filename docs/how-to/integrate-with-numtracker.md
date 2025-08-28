# Integrate With Numtracker

[Numtracker](https://github.com/DiamondLightSource/numtracker.git) is a DLS API that can be used to coordinate where detectors write their data.

## Prequisities

You will need to [get numtracker itself configured for your instrument](https://github.com/DiamondLightSource/numtracker/wiki/new_beamline). 

Blueapi needs [valid authentication configured](./authenticate.md) to communicate with numtracker. It will propogate its auth token so both blueapi and numtracker should be aware of who the user is and that they have permission to be on the instrument sessions (visits) that are intended for use.

## Configuration

Numtracker integration requires the following configuration for blueapi:
```{literalinclude} ../../tests/unit_tests/valid_example_config/numtracker.yaml
:language: yaml
```

For a more complete example see the [p46 helm chart configuration](https://github.com/epics-containers/p46-services/blob/main/services/p46-blueapi/values.yaml).

Numtracker will work for any ophyd-async [`StandardDetector`](https://blueskyproject.io/ophyd-async/main/_api/ophyd_async/ophyd_async.core.html#ophyd_async.core.StandardDetector)(s) in your project.

## Updating Blueapi and Dodal

Blueapi uses an internal [`PathProvider`](https://blueskyproject.io/ophyd-async/main/_api/ophyd_async/ophyd_async.core.html#ophyd_async.core.PathProvider) when integrated with numtracker, it does not support custom providers in from dodal modules, if your beamline definition in dodal is prefixed with a call to `set_path_provider`, it should be removed before attempting to use numtracker:

Numtracker should work with out-of-box plans that take data via runs. Opening a new run will make the `RunEngine` call numtracker and request a fresh data area. Some plans from before numtracker have a decorator that coordinates where detectors write their data: [`@attach_data_session_metadata_decorator`](https://github.com/DiamondLightSource/dodal/blob/10a9a124931901d7666659c6dbe77215d22a8bfd/src/dodal/plan_stubs/data_session.py#L60). This decorator becomes a no-op with numtracker and can be safely removed from plans.

# Scripting Plans

While the CLI can be used to query devices and run plans, it can be useful to
combine multiple plans within a better interface than bash/shell scripting.

For this, `blueapi` can be used as a library with the `BlueapiClient` wrapping
interactions with the server.

To run a standalone script, it should be possible to use [`uv`][_uv] directly.

```sh
$ uv run --with blueapi path/to/script.py
```

To include as part of an existing virtual environment, add `blueapi` using
whichever tool is being used to manage the environment, eg `uv add blueapi`,
`pip install blueapi` etc.

## Login to blueapi

The following steps require the user to have logged in blueapi. This can be done
via the `blueapi login` command from a terminal before running the script.

```sh
$ blueapi login
$ python script.py # or however you are running the script
```

It is also possible to use the `login()` command on the client with the script
although be aware this will cause the script to block waiting for the user to
login which may not be required if being run without monitoring.

## Create an instance of the client

```python
from blueapi.client import BlueapiClient

# A client can be created from either a config instance or the path to a config
# file. The minimal configuration required # is:
#  api:
#    url: https://address.of.blueapi:1234
#  stomp:
#    enabled: true
#    url: tcp://address.of.rabbitmq:61613
bc = BlueapiClient.from_config_file("/path/to/config.yaml")
```

If you are using the `login()` method in the script, it should be called before
any further interactions. If the user is already logged in, the script will
continue without prompting the user.

```python
bc.login()
```

Plans and devices are available via the `plans` and `devices` attributes of the
client. It can be useful to alias these locally to reduce the boilerplate in
scripts.

```python
plans = bc.plans
devices = bc.devices
```

## Query devices

The devices available on the server are accessible via the `devices` attribute
of the client.

```python
for device in bc.devices:
    print(device)
```

Individual devices can be accessed as attributes on the `devices` field. It can
also be useful to alias these locally.

```python
det = bc.devices.det
stage = bc.devices.stage
```

Child devices can be accessed via their parent devices

```python
stage_x = stage.x
```

Trying to access a child device that does not exist will raise an
`AttributeError`

## Run a plan

Running plans requires an instrument session. As this is unlikely to change from
one plan to another, this can be set on the client to be used for all subsequent
plans.

```python
bc.instrument_session = "cm12345-1"
```

Plans are accessible via the `plans` attribute of the client instance. They can,
for the most part, be treated as if they were local functions.

```python
bc.plans.count([bc.devices.det], num=3, delay=4.2)
```

Running a plan in this way will block until the plan is complete. If the script
is interrupted (eg via Ctrl-C) while a plan is running it will be aborted before
the script exits.

Where parameters to a plan are optional, they can be omitted from the method
call. Where parameters are required, they can be passed either as positional or
named arguments.

## Run multiple plans

Plans can then be co-ordinated using standard python constructs, eg to run a
plan multiple times

```python
for temp in range(1, 5):
    plans.set_absolute({devices.temp: temp})
    plans.count([devices.det])
```

## Passing more complex arguments

Anything passed to a plan function will be serialized into JSON before being
sent to the server. For many types you can pass the instance directly and the
serialization should handle the conversion for you.

```python
from scanspec.specs import Line

bc.plans.spec_scan(detectors=[det], spec=Line(bc.devices.stage.x, 0, 10, 11))
```

if a type does not serialize correctly, passing the JSON equivalent should be
possible instead. For instance the above is equivalent to

```python
bc.plans.spec_scan(detectors=[det], spec={
    "axis": "stage.x",
    "start": 0.0,
    "stop": 10.0,
    "num": 11,
    "type": "Line"})
```

## Add callbacks

By default there is no indication of progress while a scan is running however it
is possible to subscribe to events so that updates can be provided.

A callback should accept a single parameter which will be the event from server.
This will be one of `WorkerEvent`, `ProgressEvent` or `DataEvent`.

An example that prints data for each point could be something like

```python
def feedback(evt):
    match evt:
        case DataEvent(name="start"):
            print("Run started")
        case DataEvent(name="stop", doc={"exit_status": status}):
            print("Run complete: ", status)
        case DataEvent(name="event", doc={"seq_num": point, "data": data}):
            print(f"    Point {point}: {data}")

bc.add_callback(feedback)

bc.plans.spec_scan([bc.devices.det], Line(bc.devices.stage.x, 0, 1, 11))
```

The above prints the following as the scan progresses

```
Run started
    Point 1: {'stage-x': 0.0}
    Point 2: {'stage-x': 0.1}
    Point 3: {'stage-x': 0.2}
    Point 4: {'stage-x': 0.3}
    Point 5: {'stage-x': 0.4}
    Point 6: {'stage-x': 0.5}
    Point 7: {'stage-x': 0.6}
    Point 8: {'stage-x': 0.7000000000000001}
    Point 9: {'stage-x': 0.8}
    Point 10: {'stage-x': 0.9}
    Point 11: {'stage-x': 1.0}
Run complete:  success
```

The `add_callback` method returns an ID that can be used to remove the callback

```python
# Add the callback and record the handle
hnd = bc.add_callback(callback_function)

# remove the callback using the returned handle
bc.remove_callback(hnd)
```

[_uv]:https://docs.astral.sh/uv/

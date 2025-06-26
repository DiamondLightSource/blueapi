# Run a Plan

:::{note}
You will need [a running server connected to a message bus](./run-bus.md) to complete this tutorial.
:::

With a [running worker](./quickstart.md), you can then run a plan. In a new terminal:

```
blueapi controller run -i cm12345-1 sleep '{"time": 5}'
```

## Example Plans

Move a Motor

```
blueapi -c stomp.yaml controller run move \
'{
    "moves": {"x": 5}
}'
```

Take a Snapshot on a Detector

```
blueapi -c stomp.yaml controller run count \
'{
    "detectors": ["image_det"]
}'
```

Run a Scan

```
blueapi -c stomp.yaml controller run scan \
'{
    "detectors": ["image_det"], 
    "spec": {
        "type": "Line", 
        "axis": "x", 
        "start": 0, 
        "stop": 10, 
        "num": 10
    }, 
    "axes_to_move": {"x": "x"}
}'
```

The names of the devices used (`"image_det"` and `"x"`) can be found via:

```
blueapi controller devices
```

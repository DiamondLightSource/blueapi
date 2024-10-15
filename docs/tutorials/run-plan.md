# Run a Plan

With a [running worker](./quickstart.md), you can then run a plan. In a new terminal:

```
blueapi controller run sleep '{"time": 5}'
```

Or to run a full scan:

```
blueapi controller run scan '{"detectors": ["image_det"], spec: {"type": "Line", "axis": "x", "start": 0, "stop": 10, "num": 10}}'
```

The names of the devices used (`"image_det"` and `"x"`) can be found via:

```
blueapi controller devices
```

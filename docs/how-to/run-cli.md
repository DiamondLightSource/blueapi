# Control the Worker via the CLI

The worker comes with a minimal CLI client for basic control. It should be noted that this is 
a test/development/debugging tool and not meant for production!

    `./run-container` and `../tutorials/installation`




## Basic Introspection

The worker can tell you which plans and devices are available via:
``` 
    blueapi controller plans
    blueapi controller devices

By default, the CLI will talk to the worker via a message broker on `tcp://localhost:61613`,
but you can customize this.

```
    blueapi controller -h my.host -p 61614 plans
```

## Running Plans

You can run a plan and pass arbitrary JSON parameters.
``` 
    # Run the sleep plan
    blueapi controller run sleep '{"time": 5.0}'

    # Run the count plan
    blueapi controller run count '{"detectors": ["current_det", "image_det"]}'
```

The command will block until the plan is finished and will forward error/status messages 
from the server.

See also [Full CLI reference](../reference/cli.md)

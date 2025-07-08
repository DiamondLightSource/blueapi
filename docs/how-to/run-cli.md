# Control the Worker via the CLI

Blueapi comes with a minimal CLI client for basic control/debugging.

## Basic Introspection

The worker can tell you which plans and devices are available via:
``` 
blueapi controller plans
blueapi controller devices
```

By default, the CLI will talk to the worker via a message broker on `tcp://localhost:61613`,
but you can customize this via a [configuration file](./configure-app.md).

```yaml
# custom-address.yaml

api:
    url: http://example.com:8082
```

Then run

```
blueapi -c custom-address.yaml controller plans
```

The CLI has a number of features including [running plans](../tutorials/run-plan.md) and 

See also [Full CLI reference](../reference/cli.md)

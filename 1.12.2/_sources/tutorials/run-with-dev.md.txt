# Run/Debug in a Developer Environment

Assuming you have setup a developer environment, you can run a development version of the bluesky worker.

## Start Bluesky Worker

Ensure you are inside your virtual environment:

```
source venv/bin/activate
```

You will need to follow the instructions for setting up RabbitMQ as in [instructions for setting up RabbitMQ](run-bus.md).

The worker will be available from the command line (`blueapi serve`), but can be started from vscode with additional
debugging capabilities.

1. Navigate to "Run and Debug" in the left hand menu.
2. Select "Worker Service" from the debug configuration.
3. Click the green "Run Button"

[debug in vscode](../images/debug-vscode.png)

:::{seealso}
[Scratch Area](../how-to/edit-live.md) for in-the-loop development of plans and devices
:::

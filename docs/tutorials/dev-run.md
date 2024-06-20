# Run/Debug in a Developer Environment

Assuming you have setup a developer environment, you can run a development version of the bluesky worker.

## Start Bluesky Worker

Ensure you are inside your virtual environment:

```
    source venv/bin/activate
```

You will need to follow the instructions for setting up ActiveMQ as in [run cli instructions](../how-to/run-cli.md).

The worker will be available from the command line (`blueapi serve`), but can be started from vscode with additional
debugging capabilities.

1. Navigate to "Run and Debug" in the left hand menu.
2. Select "Worker Service" from the debug configuration.
3. Click the green "Run Button"

[debug in vscode](../images/debug-vscode.png)

## Develop devices

When you select the 'scratch directory' option - where you have devices (dodal) and plans (BLxx-beamline) in a place like `/dls_sw/BLXX/software/blueapi/scratch`, then the list of devices available will refresh without interfacing with the K8S cluster. Just run the command `blueapi env -r` or `blueapi env --reload`.

With this setup you get a developer loop: "write devices - write plans - test them with blueapi".

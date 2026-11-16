# Run/Debug in a Developer Environment

The recommended developer environment is the [devcontainer](https://code.visualstudio.com/docs/devcontainers/containers) defined in this repository. It provides `uv`, `just` and `helm`, and installs blueapi with its development dependencies, so you do not need to set up Python yourself.

## Open the Devcontainer

You need VS Code with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers), and either podman or docker.

:::{seealso}
[Setup Developer Environment](https://diamondlightsource.github.io/python-copier-template/main/how-to/dev-install.html) in the python-copier-template documentation for the prerequisites, including the podman setup needed at Diamond.
:::

1. Clone the repository and open it in VS Code with `code .`
2. Click "Reopen in Container" when prompted. If VS Code is already open, press Ctrl+Shift+P and run "Dev Containers: Reopen in Container".

The first start is slower than later ones, because the image has to be built and the dependencies downloaded.

When the container is created it runs `uv sync` to build a virtual environment, then installs the pre-commit hooks with `prek`. The virtual environment is already on the `PATH` of every VS Code terminal, so there is nothing to activate: `blueapi`, `pytest`, `tox` and `prek` can be run directly. Run `uv sync` again after pulling changes that alter the dependencies.

## Start the Server

In a terminal inside the container, run:

```
blueapi serve
```

This uses the default configuration, which has no plans or devices and needs no other services. To use your own configuration, pass it with `-c`:

```
blueapi -c path/to/config.yaml serve
```

In a second terminal, check that the server responds:

```
blueapi controller plans
```

## Debug in VS Code

The repository includes these launch configurations in `.vscode/launch.json`:

| Configuration | What it runs |
| --- | --- |
| Blueapi Server | `blueapi serve` with the default configuration |
| Blueapi Server (Custom Config) | `blueapi --config <path> serve`. Prompts for the path, and sets the EPICS name server variables for the simulated IOCs in the system test services |
| Blueapi Controller | `blueapi controller <arguments>`. Prompts for the arguments |
| Blueapi Controller (Custom Config) | The same, with a configuration file |
| Debug Unit Test | Used when you debug a test from the Testing panel |

To start one:

1. Navigate to "Run and Debug" in the left hand menu.
2. Select the configuration from the drop-down.
3. Click the green run button.

The [screenshot](../images/debug-vscode.png) shows where to find each of these. It was taken with an older set of configurations, so the name in the drop-down differs.

## Connect to Other Services

A configuration that enables the message bus, numtracker, Tiled or authentication needs those services to be running. The devcontainer does not contain podman or docker, so start them from a terminal on the host with `just compose`, as described in [Run BlueAPI and connect to services locally](./just-run-blueapi-and-services-locally.md).

The devcontainer is started with host networking, so on Linux the services are then available on `localhost` inside it. From there, `just serve` starts the server with the configuration used by the system tests.

## Run the Checks

```
just lint    # regenerate the schemas, then run the pre-commit checks and type checking
just unit    # run the unit tests
tox -p       # what CI runs: pre-commit checks, type checking, unit tests and the docs build
```

:::{seealso}
[Scratch Area](../how-to/1.5%20edit-live.md) for in-the-loop development of plans and devices
:::

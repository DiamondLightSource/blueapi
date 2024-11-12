import json
import logging
import sys
from functools import wraps
from pathlib import Path
from pprint import pprint

import click
from bluesky.callbacks.best_effort import BestEffortCallback
from bluesky_stomp.messaging import MessageContext, StompClient
from bluesky_stomp.models import Broker
from observability_utils.tracing import setup_tracing
from pydantic import ValidationError
from requests.exceptions import ConnectionError

from blueapi import __version__
from blueapi.cli.format import OutputFormat
from blueapi.client.client import BlueapiClient
from blueapi.client.event_bus import AnyEvent, BlueskyStreamingError, EventBusClient
from blueapi.client.rest import BlueskyRemoteControlError
from blueapi.config import (
    ApplicationConfig,
    CLIClientConfig,
    ConfigLoader,
)
from blueapi.core import OTLP_EXPORT_ENABLED, DataEvent
from blueapi.service.authentication import SessionManager
from blueapi.worker import ProgressEvent, Task, WorkerEvent

from .scratch import setup_scratch
from .updates import CliEventRenderer


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="blueapi")
@click.option(
    "-c", "--config", type=Path, help="Path to configuration YAML file", multiple=True
)
@click.pass_context
def main(ctx: click.Context, config: Path | None | tuple[Path, ...]) -> None:
    # if no command is supplied, run with the options passed

    config_loader = ConfigLoader(ApplicationConfig)
    if config is not None:
        configs = (config,) if isinstance(config, Path) else config
        for path in configs:
            if path.exists():
                config_loader.use_values_from_yaml(path)
            else:
                raise FileNotFoundError(f"Cannot find file: {path}")

    ctx.ensure_object(dict)
    loaded_config: ApplicationConfig = config_loader.load()

    ctx.obj["config"] = loaded_config
    logging.basicConfig(
        format="%(asctime)s - %(message)s", level=loaded_config.logging.level
    )

    if ctx.invoked_subcommand is None:
        print("Please invoke subcommand!")


@main.command(name="schema")
@click.option("-o", "--output", type=Path, help="Path to file to save the schema")
@click.option(
    "-u",
    "--update",
    type=bool,
    is_flag=True,
    help="[Development only] update the schema in the documentation",
)
def schema(output: Path | None = None, update: bool = False) -> None:
    """Only import the service functions when starting the service or generating
    the schema, not the controller as a new FastAPI app will be started each time.
    """
    from blueapi.service.openapi import (
        DOCS_SCHEMA_LOCATION,
        generate_schema,
        print_schema_as_yaml,
        write_schema_as_yaml,
    )

    """Generate the schema for the REST API"""
    schema = generate_schema()

    if update:
        output = DOCS_SCHEMA_LOCATION
    if output is not None:
        write_schema_as_yaml(output, schema)
    else:
        print_schema_as_yaml(schema)


@main.command(name="serve")
@click.pass_obj
def start_application(obj: dict):
    """Run a worker that accepts plans to run"""
    config: ApplicationConfig = obj["config"]

    """Only import the service functions when starting the service or generating
    the schema, not the controller as a new FastAPI app will be started each time.
    """
    from blueapi.service.main import start

    """
    Set up basic automated instrumentation for the FastAPI app, creating the
    observability context.
    """
    setup_tracing("BlueAPI", OTLP_EXPORT_ENABLED)
    start(config)


@main.group()
@click.option(
    "-o",
    "--output",
    type=click.Choice([o.name.lower() for o in OutputFormat]),
    default="compact",
)
@click.pass_context
def controller(ctx: click.Context, output: str) -> None:
    """Client utility for controlling and introspecting the worker"""

    setup_tracing("BlueAPICLI", OTLP_EXPORT_ENABLED)
    if ctx.invoked_subcommand is None:
        print("Please invoke subcommand!")
        return

    ctx.ensure_object(dict)
    config: ApplicationConfig = ctx.obj["config"]
    ctx.obj["fmt"] = OutputFormat(output)
    ctx.obj["client"] = BlueapiClient.from_config(config)


def check_connection(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except ConnectionError:
            print("Failed to establish connection to FastAPI server.")

    return wrapper


@controller.command(name="plans")
@check_connection
@click.pass_obj
def get_plans(obj: dict) -> None:
    """Get a list of plans available for the worker to use"""
    client: BlueapiClient = obj["client"]
    obj["fmt"].display(client.get_plans())


@controller.command(name="devices")
@check_connection
@click.pass_obj
def get_devices(obj: dict) -> None:
    """Get a list of devices available for the worker to use"""
    client: BlueapiClient = obj["client"]
    obj["fmt"].display(client.get_devices())


@controller.command(name="listen")
@check_connection
@click.pass_obj
def listen_to_events(obj: dict) -> None:
    """Listen to events output by blueapi"""
    config: ApplicationConfig = obj["config"]
    if config.stomp is not None:
        event_bus_client = EventBusClient(
            StompClient.for_broker(
                broker=Broker(
                    host=config.stomp.host,
                    port=config.stomp.port,
                    auth=config.stomp.auth,
                )
            )
        )
    else:
        raise RuntimeError("Message bus needs to be configured")

    fmt = obj["fmt"]

    def on_event(
        event: WorkerEvent | ProgressEvent | DataEvent,
        context: MessageContext,
    ) -> None:
        fmt.display(event)

    print(
        "Subscribing to all bluesky events from "
        f"{config.stomp.host}:{config.stomp.port}",
        file=sys.stderr,
    )
    with event_bus_client:
        event_bus_client.subscribe_to_all_events(on_event)
        print("Press enter to exit", file=sys.stderr)
        input()


@controller.command(name="run")
@click.argument("name", type=str)
@click.argument("parameters", type=str, required=False)
@click.option(
    "-t",
    "--timeout",
    type=float,
    help="Timeout for the plan in seconds. None hangs forever",
    default=None,
)
@check_connection
@click.pass_obj
def run_plan(
    obj: dict, name: str, parameters: str | None, timeout: float | None
) -> None:
    """Run a plan with parameters"""
    client: BlueapiClient = obj["client"]

    parameters = parameters or "{}"
    task_id = ""
    parsed_params = json.loads(parameters) if isinstance(parameters, str) else {}

    progress_bar = CliEventRenderer()
    callback = BestEffortCallback()

    def on_event(event: AnyEvent) -> None:
        if isinstance(event, ProgressEvent):
            progress_bar.on_progress_event(event)
        elif isinstance(event, DataEvent):
            callback(event.name, event.doc)

    try:
        task = Task(name=name, params=parsed_params)
        resp = client.run_task(task, on_event=on_event)
    except ValidationError as e:
        pprint(f"failed to validate the task parameters, {task_id}, error: {e}")
        return
    except (BlueskyRemoteControlError, BlueskyStreamingError) as e:
        pprint(f"server error with this message: {e}")
        return
    except ValueError:
        pprint("task could not run")
        return

    pprint(resp.model_dump())
    if resp.task_status is not None and not resp.task_status.task_failed:
        print("Plan Succeeded")


@controller.command(name="state")
@check_connection
@click.pass_obj
def get_state(obj: dict) -> None:
    """Print the current state of the worker"""

    client: BlueapiClient = obj["client"]
    print(client.get_state().name)


@controller.command(name="pause")
@click.option("--defer", is_flag=True, help="Defer the pause until the next checkpoint")
@check_connection
@click.pass_obj
def pause(obj: dict, defer: bool = False) -> None:
    """Pause the execution of the current task"""

    client: BlueapiClient = obj["client"]
    pprint(client.pause(defer=defer))


@controller.command(name="resume")
@check_connection
@click.pass_obj
def resume(obj: dict) -> None:
    """Resume the execution of the current task"""

    client: BlueapiClient = obj["client"]
    pprint(client.resume())


@controller.command(name="abort")
@check_connection
@click.argument("reason", type=str, required=False)
@click.pass_obj
def abort(obj: dict, reason: str | None = None) -> None:
    """
    Abort the execution of the current task, marking any ongoing runs as failed,
    with optional reason
    """

    client: BlueapiClient = obj["client"]
    pprint(client.abort(reason=reason))


@controller.command(name="stop")
@check_connection
@click.pass_obj
def stop(obj: dict) -> None:
    """
    Stop the execution of the current task, marking as ongoing runs as success
    """

    client: BlueapiClient = obj["client"]
    pprint(client.stop())


@controller.command(name="env")
@check_connection
@click.option(
    "-r",
    "--reload",
    is_flag=True,
    help="Reload the current environment",
    default=False,
)
@click.option(
    "-t",
    "--timeout",
    type=float,
    help="Timeout to wait for reload in seconds, defaults to 10",
    default=10.0,
)
@click.pass_obj
def env(
    obj: dict,
    reload: bool,
    timeout: float | None,
) -> None:
    """
    Inspect or restart the environment
    """

    assert isinstance(client := obj["client"], BlueapiClient)
    if reload:
        # Reload the environment if needed
        print("Reloading environment")
        status = client.reload_environment(timeout=timeout)
        print("Environment is initialized")
    else:
        status = client.get_environment()
    print(status)


@main.command(name="setup-scratch")
@click.pass_obj
def scratch(obj: dict) -> None:
    config: ApplicationConfig = obj["config"]
    if config.scratch is not None:
        setup_scratch(config.scratch)
    else:
        raise KeyError("No scratch config supplied")


@main.command(name="login")
@click.pass_obj
def login(obj: dict) -> None:
    config: ApplicationConfig = obj["config"]
    if isinstance(config.oidc, CLIClientConfig):
        print("Logging in")
        auth: SessionManager = SessionManager(config.oidc)
        try:
            auth.start_device_flow()
        except Exception as e:
            print(f"Failed to login: {e}")
    else:
        print("Please provide configuration to login!")


@main.command(name="logout")
@click.pass_obj
def logout(obj: dict) -> None:
    config: ApplicationConfig = obj["config"]
    if isinstance(config.oidc, CLIClientConfig):
        auth: SessionManager = SessionManager(server_config=config.oidc)
        auth.logout()
        print("Logged out")
    else:
        print("Please provide configuration to logout!")

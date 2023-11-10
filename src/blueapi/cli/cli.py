import json
import logging
from collections import deque
from functools import wraps
from pathlib import Path
from pprint import pprint
from typing import Optional, Tuple, Union

import click
from requests.exceptions import ConnectionError

from blueapi import __version__
from blueapi.cli.amq import AmqClient
from blueapi.config import ApplicationConfig, ConfigLoader
from blueapi.core import DataEvent
from blueapi.messaging import MessageContext
from blueapi.messaging.stomptemplate import StompMessagingTemplate
from blueapi.service.main import start
from blueapi.service.model import WorkerTask
from blueapi.service.openapi import (
    DOCS_SCHEMA_LOCATION,
    generate_schema,
    print_schema_as_yaml,
    write_schema_as_yaml,
)
from blueapi.worker import ProgressEvent, RunPlan, WorkerEvent, WorkerState

from .rest import BlueapiRestClient


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="blueapi")
@click.option(
    "-c", "--config", type=Path, help="Path to configuration YAML file", multiple=True
)
@click.pass_context
def main(ctx: click.Context, config: Union[Optional[Path], Tuple[Path, ...]]) -> None:
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
    logging.basicConfig(level=loaded_config.logging.level)

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
def schema(output: Optional[Path] = None, update: bool = False) -> None:
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

    start(config)


@main.group()
@click.pass_context
def controller(ctx: click.Context) -> None:
    """Client utility for controlling and introspecting the worker"""

    if ctx.invoked_subcommand is None:
        print("Please invoke subcommand!")
        return

    ctx.ensure_object(dict)
    config: ApplicationConfig = ctx.obj["config"]
    ctx.obj["rest_client"] = BlueapiRestClient(config.api)


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
    client: BlueapiRestClient = obj["rest_client"]
    pprint(client.get_plans().dict())


@controller.command(name="devices")
@check_connection
@click.pass_obj
def get_devices(obj: dict) -> None:
    """Get a list of devices available for the worker to use"""
    client: BlueapiRestClient = obj["rest_client"]
    pprint(client.get_devices().dict())


@controller.command(name="listen")
@check_connection
@click.pass_obj
def listen_to_events(obj: dict) -> None:
    """Listen to events output by blueapi"""
    config: ApplicationConfig = obj["config"]
    amq_client = AmqClient(StompMessagingTemplate.autoconfigured(config.stomp))

    def on_event(
        context: MessageContext,
        event: Union[WorkerEvent, ProgressEvent, DataEvent],
    ) -> None:
        converted = json.dumps(event.dict(), indent=2)
        print(converted)

    print(
        "Subscribing to all bluesky events from "
        f"{config.stomp.host}:{config.stomp.port}"
    )
    with amq_client:
        amq_client.subscribe_to_all_events(on_event)
        input("Press enter to exit")


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
    obj: dict, name: str, parameters: Optional[str], timeout: Optional[float]
) -> None:
    """Run a plan with parameters"""
    config: ApplicationConfig = obj["config"]
    client: BlueapiRestClient = obj["rest_client"]

    logger = logging.getLogger(__name__)

    amq_client = AmqClient(StompMessagingTemplate.autoconfigured(config.stomp))
    finished_event: deque[WorkerEvent] = deque()

    def store_finished_event(event: WorkerEvent) -> None:
        if event.is_complete():
            finished_event.append(event)

    parameters = parameters or "{}"
    task = RunPlan(name=name, params=json.loads(parameters))

    resp = client.create_task(task)
    task_id = resp.task_id

    with amq_client:
        amq_client.subscribe_to_topics(task_id, on_event=store_finished_event)
        updated = client.update_worker_task(WorkerTask(task_id=task_id))

        amq_client.wait_for_complete(timeout=timeout)

        if amq_client.timed_out:
            logger.error(f"Plan did not complete within {timeout} seconds")
            return

    process_event_after_finished(finished_event.pop(), logger)
    pprint(updated.dict())


@controller.command(name="state")
@check_connection
@click.pass_obj
def get_state(obj: dict) -> None:
    """Print the current state of the worker"""

    client: BlueapiRestClient = obj["rest_client"]
    pprint(client.get_state())


@controller.command(name="pause")
@click.option("--defer", is_flag=True, help="Defer the pause until the next checkpoint")
@check_connection
@click.pass_obj
def pause(obj: dict, defer: bool = False) -> None:
    """Pause the execution of the current task"""

    client: BlueapiRestClient = obj["rest_client"]
    pprint(client.set_state(WorkerState.PAUSED, defer=defer))


@controller.command(name="resume")
@check_connection
@click.pass_obj
def resume(obj: dict) -> None:
    """Resume the execution of the current task"""

    client: BlueapiRestClient = obj["rest_client"]
    pprint(client.set_state(WorkerState.RUNNING))


@controller.command(name="abort")
@check_connection
@click.argument("reason", type=str, required=False)
@click.pass_obj
def abort(obj: dict, reason: Optional[str] = None) -> None:
    """
    Abort the execution of the current task, marking any ongoing runs as failed,
    with optional reason
    """

    client: BlueapiRestClient = obj["rest_client"]
    pprint(client.cancel_current_task(state=WorkerState.ABORTING, reason=reason))


@controller.command(name="stop")
@check_connection
@click.pass_obj
def stop(obj: dict) -> None:
    """
    Stop the execution of the current task, marking as ongoing runs as success
    """

    client: BlueapiRestClient = obj["rest_client"]
    pprint(client.cancel_current_task(state=WorkerState.STOPPING))


# helper function
def process_event_after_finished(event: WorkerEvent, logger: logging.Logger):
    if event.is_error():
        logger.info("Failed with errors: \n")
        for error in event.errors:
            logger.error(error)
        return
    if len(event.warnings) != 0:
        logger.info("Passed with warnings: \n")
        for warning in event.warnings:
            logger.warn(warning)
        return

    logger.info("Plan passed")

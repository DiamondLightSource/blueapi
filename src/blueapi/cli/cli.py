import json
import logging
from functools import wraps
from pathlib import Path
from pprint import pprint
from typing import Optional

import click
from requests.exceptions import ConnectionError

from blueapi import __version__
from blueapi.config import ApplicationConfig, ConfigLoader
from blueapi.service.main import start
from blueapi.service.model import WorkerTask
from blueapi.service.openapi import (
    DOCS_SCHEMA_LOCATION,
    generate_schema,
    print_schema_as_yaml,
    write_schema_as_yaml,
)
from blueapi.worker import RunPlan

from .rest import BlueapiRestClient


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="blueapi")
@click.option("-c", "--config", type=Path, help="Path to configuration YAML file")
@click.pass_context
def main(ctx: click.Context, config: Optional[Path]) -> None:
    # if no command is supplied, run with the options passed

    config_loader = ConfigLoader(ApplicationConfig)
    if config is not None:
        if config.exists():
            config_loader.use_values_from_yaml(config)
        else:
            raise FileNotFoundError(f"Cannot find file: {config}")

    ctx.ensure_object(dict)
    ctx.obj["config"] = config_loader.load()

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
    start(obj["config"])


@main.group()
@click.pass_context
def controller(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        print("Please invoke subcommand!")
        return

    ctx.ensure_object(dict)
    config: ApplicationConfig = ctx.obj["config"]
    ctx.obj["rest_client"] = BlueapiRestClient(config.api)
    logging.basicConfig(level=config.logging.level)


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
    client: BlueapiRestClient = obj["rest_client"]
    pprint(client.get_plans().dict())


@controller.command(name="devices")
@check_connection
@click.pass_obj
def get_devices(obj: dict) -> None:
    client: BlueapiRestClient = obj["rest_client"]
    pprint(client.get_devices().dict())


@controller.command(name="run")
@click.argument("name", type=str)
@click.argument("parameters", type=str, required=False)
@check_connection
@click.pass_obj
def run_plan(obj: dict, name: str, parameters: Optional[str]) -> None:
    client: BlueapiRestClient = obj["rest_client"]
    parameters = parameters or "{}"
    task = RunPlan(name=name, params=json.loads(parameters))

    resp = client.create_task(task)
    task_id = resp.task_id
    updated = client.update_worker_task(WorkerTask(task_id=task_id))
    pprint(updated.dict())


@controller.command(name="state")
@check_connection
@click.pass_obj
def get_state(obj: dict) -> None:
    client: BlueapiRestClient = obj["rest_client"]
    pprint(client.get_state())

import json
import logging
from functools import wraps
from pathlib import Path
from pprint import pprint
from typing import Optional

import click
import requests
from requests.exceptions import ConnectionError

from blueapi import __version__
from blueapi.config import ApplicationConfig, ConfigLoader
from blueapi.service.main import start


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
    config: ApplicationConfig = obj["config"]

    resp = requests.get(f"http://{config.api.host}:{config.api.port}/plans")
    print(f"Response returned with {resp.status_code}: ")
    pprint(resp.json())


@controller.command(name="devices")
@check_connection
@click.pass_obj
def get_devices(obj: dict) -> None:
    config: ApplicationConfig = obj["config"]

    resp = requests.get(f"http://{config.api.host}:{config.api.port}/devices")
    print(f"Response returned with {resp.status_code}: ")
    pprint(resp.json())


@controller.command(name="run")
@click.argument("name", type=str)
@click.argument("parameters", type=str, required=False)
@check_connection
@click.pass_obj
def run_plan(obj: dict, name: str, parameters: Optional[str]) -> None:
    config: ApplicationConfig = obj["config"]
    parameters = parameters or "{}"

    resp = requests.put(
        f"http://{config.api.host}:{config.api.port}/task/{name}",
        json=json.loads(parameters),
    )
    print(f"Response returned with {resp.status_code}")


@controller.command(name="state")
@check_connection
@click.pass_obj
def get_state(obj: dict) -> None:
    config: ApplicationConfig = obj["config"]

    resp = requests.get(f"http://{config.api.host}:{config.api.port}/worker/state")
    print(f"Response returned with {resp.status_code}: ")
    pprint(resp.json())

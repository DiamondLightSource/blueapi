import json
import logging
from pprint import pprint

import click
import requests
from requests.exceptions import ConnectionError

from blueapi import __version__
from blueapi.config import ApplicationConfig, ConfigLoader
from blueapi.messaging import StompMessagingTemplate
from blueapi.service.main import app

from pathlib import Path
from typing import Optional


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="blueapi")
@click.option("-c", "--config", type=Path, help="Path to configuration YAML file")
@click.pass_context
def main(ctx, config: Optional[Path]) -> None:
    # if no command is supplied, run with the options passed
    config_loader = ConfigLoader(ApplicationConfig)
    if config is not None:
        config_loader.use_values_from_yaml(config)

    ctx.ensure_object(dict)
    ctx.obj["config"] = config_loader.load()

    if ctx.invoked_subcommand is None:
        print("Please invoke subcommand!")


@click.version_option(version=__version__)
@main.command(name="run")
@click.pass_obj
def start_application(obj: dict):
    import uvicorn

    config: ApplicationConfig = obj["config"]
    uvicorn.run(app, host=settings.host, port=int(settings.port))


@main.group()
@click.pass_context
def controller(ctx) -> None:
    if ctx.invoked_subcommand is None:
        print("Please invoke subcommand!")
        return

    ctx.ensure_object(dict)
    config: ApplicationConfig = ctx.obj["config"]
    logging.basicConfig(level=config.logging.level)


def check_connection(func):
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except ConnectionError:
            print("Failed to establish connection.")

    return wrapper


@controller.command(name="plans")
@check_connection
def get_plans() -> None:
    resp = requests.get(f"{settings.url}/plans")
    print(f"Response returned with {resp.status_code}: ")
    pprint(resp.json())


@controller.command(name="devices")
@check_connection
def get_devices() -> None:
    resp = requests.get(f"{settings.url}/devices")
    print(f"Response returned with {resp.status_code}: ")
    pprint(resp.json())


@controller.command(name="run")
@click.argument("name", type=str)
@click.option("-p", "--parameters", type=str, help="Parameters as valid JSON")
@check_connection
def run_plan(name: str, parameters: str) -> None:
    resp = requests.put(f"{settings.url}/task/{name}", json=json.loads(parameters))
    print(f"Response returned with {resp.status_code}: ")
    pprint(resp.json())

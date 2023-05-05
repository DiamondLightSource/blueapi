import json
import logging
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
def main(ctx, config: Optional[Path]) -> None:
    # if no command is supplied, run with the options passed

    config_loader = ConfigLoader(ApplicationConfig)
    if config is not None:
        config_loader.use_values_from_yaml(config)

    ctx.ensure_object(dict)
    ctx.obj["config_loader"] = config_loader

    if ctx.invoked_subcommand is None:
        print("Please invoke subcommand!")


@main.command(name="run")
@click.pass_obj
def start_application(obj: dict):
    start(obj["config_loader"])


@main.command(name="worker", deprecated=True)
@click.pass_obj
def deprecated_start_application(obj: dict):
    print("Please use run command instead.\n")
    start(obj["config_loader"])


@main.group()
@click.pass_context
def controller(ctx) -> None:
    if ctx.invoked_subcommand is None:
        print("Please invoke subcommand!")
        return

    ctx.ensure_object(dict)
    config_loader: ConfigLoader[ApplicationConfig] = ctx.obj["config_loader"]
    config: ApplicationConfig = config_loader.load()
    logging.basicConfig(level=config.logging.level)


def check_connection(func):
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
    config_loader: ConfigLoader[ApplicationConfig] = obj["config_loader"]
    config: ApplicationConfig = config_loader.load()

    resp = requests.get(f"http://{config.api.host}:{config.api.port}/plans")
    print(f"Response returned with {resp.status_code}: ")
    pprint(resp.json())


@controller.command(name="devices")
@check_connection
@click.pass_obj
def get_devices(obj: dict) -> None:
    config_loader: ConfigLoader[ApplicationConfig] = obj["config_loader"]
    config: ApplicationConfig = config_loader.load()
    resp = requests.get(f"http://{config.api.host}:{config.api.port}/devices")
    print(f"Response returned with {resp.status_code}: ")
    pprint(resp.json())


@controller.command(name="run")
@click.argument("name", type=str)
@click.option("-p", "--parameters", type=str, help="Parameters as valid JSON")
@check_connection
@click.pass_obj
def run_plan(obj: dict, name: str, parameters: str) -> None:
    config_loader: ConfigLoader[ApplicationConfig] = obj["config_loader"]
    config: ApplicationConfig = config_loader.load()
    resp = requests.put(
        f"http://{config.api.host}:{config.api.port}/task/{name}",
        json=json.loads(parameters),
    )
    print(f"Response returned with {resp.status_code}: ")
    pprint(resp.json())

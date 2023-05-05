import json
import logging
from pathlib import Path
from typing import Optional

import click

from blueapi import __version__
from blueapi.config import ApplicationConfig, ConfigLoader
from blueapi.messaging import StompMessagingTemplate

from .amq import AmqClient
from .updates import CliEventRenderer


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
        print(f"Using configuration file at: {config}. Please invoke subcommand!")


@main.command(name="worker")
@click.pass_obj
def start_worker(obj: dict) -> None:
    from blueapi.service import start

    config: ApplicationConfig = obj["config"]
    start(config)


@main.group()
@click.pass_context
def controller(ctx) -> None:
    if ctx.invoked_subcommand is None:
        print("Please invoke subcommand!")
        return

    ctx.ensure_object(dict)
    config: ApplicationConfig = ctx.obj["config"]
    logging.basicConfig(level=config.logging.level)
    client = AmqClient(StompMessagingTemplate.autoconfigured(config.stomp))
    ctx.obj["client"] = client
    client.app.connect()


@controller.command(name="plans")
@click.pass_context
def get_plans(ctx) -> None:
    client: AmqClient = ctx.obj["client"]
    plans = client.get_plans()
    print("PLANS")
    for plan in plans.plans:
        print("\t" + plan.name)


@controller.command(name="devices")
@click.pass_context
def get_devices(ctx) -> None:
    client: AmqClient = ctx.obj["client"]
    print(client.get_devices().devices)


@controller.command(name="run")
@click.argument("name", type=str)
@click.option("-p", "--parameters", type=str, help="Parameters as valid JSON")
@click.pass_context
def run_plan(ctx, name: str, parameters: str) -> None:
    client: AmqClient = ctx.obj["client"]
    renderer = CliEventRenderer()
    client.run_plan(
        name,
        json.loads(parameters),
        renderer.on_worker_event,
        renderer.on_progress_event,
        timeout=120.0,
    )

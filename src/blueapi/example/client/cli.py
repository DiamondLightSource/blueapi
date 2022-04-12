import json

import click

from blueapi import __version__
from blueapi.messaging import StompMessagingApp

from .amq import AmqClient


@click.group(invoke_without_command=True)
@click.option(
    "-u",
    "--url",
    type=str,
    help="REST API URL",
    default="http://localhost:8000",
)
@click.version_option(version=__version__)
@click.pass_context
def main(ctx, url: str) -> None:
    # if no command is supplied, run with the options passed
    if ctx.invoked_subcommand is None:
        print("Please invoke subcommand!")
    ctx.ensure_object(dict)
    client = AmqClient(StompMessagingApp())
    ctx.obj["client"] = client
    client.app.connect()


@main.command(name="plans")
@click.pass_context
def get_plans(ctx) -> None:
    client: AmqClient = ctx.obj["client"]
    plans = client.get_plans()
    print("PLANS")
    for plan in plans:
        print("\t" + plan["name"])  # type: ignore


@main.command(name="abilities")
@click.pass_context
def get_abilities(ctx) -> None:
    client: AmqClient = ctx.obj["client"]
    print(client.get_abilities())


@main.command(name="run")
@click.argument("name", type=str)
@click.option("-p", "--parameters", type=str, help="Parameters as valid JSON")
@click.pass_context
def run_plan(ctx, name: str, parameters: str) -> None:
    client: AmqClient = ctx.obj["client"]
    client.run_plan(name, json.loads(parameters))

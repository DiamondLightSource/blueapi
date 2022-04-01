import asyncio
import json

import click

from blueapi import __version__

from .rest import RestClient


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
    ctx.obj["rest_client"] = RestClient(url)


@main.command(name="plans")
@click.pass_context
def get_plans(ctx) -> None:
    client: RestClient = ctx.obj["rest_client"]
    plans = asyncio.run(client.get_plans())
    print("PLANS")
    for plan in plans:
        print("\t" + plan["name"])  # type: ignore


@main.command(name="abilities")
@click.pass_context
def get_abilities(ctx) -> None:
    client: RestClient = ctx.obj["rest_client"]
    print(asyncio.run(client.get_abilities()))


@main.command(name="plan")
@click.argument("name", type=str)
@click.pass_context
def get_plan(ctx, name: str) -> None:
    client: RestClient = ctx.obj["rest_client"]
    plan = asyncio.run(client.get_plan(name))

    name = plan["name"]  # type: ignore
    schema = plan["schema"]  # type: ignore
    print(f"PLAN: {name}")

    from pprint import pprint

    pprint(schema)


@main.command(name="run")
@click.argument("name", type=str)
@click.option("-p", "--parameters", type=str, help="Parameters as valid JSON")
@click.pass_context
def run_plan(ctx, name: str, parameters: str) -> None:
    client: RestClient = ctx.obj["rest_client"]
    print(asyncio.run(client.run_plan(name, json.loads(parameters))))

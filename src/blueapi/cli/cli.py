import json
import logging
from pathlib import Path
from typing import Optional

import click

from blueapi import __version__
from blueapi.config import StompConfig, AMQPConfig
from blueapi.messaging import StompMessagingTemplate, AMQPMessagingTemplate

from .amq import MessagingClient
from .updates import CliEventRenderer


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="blueapi")
@click.pass_context
def main(ctx) -> None:
    # if no command is supplied, run with the options passed
    if ctx.invoked_subcommand is None:
        print("Please invoke subcommand!")


@main.command(name="worker")
@click.option("-c", "--config", type=Path, help="Path to configuration YAML file")
def start_worker(config: Optional[Path]):
    from blueapi.service import start

    start(config)


@main.group()
@click.option(
    "-h",
    "--host",
    type=str,
    help="Broker host",
    default="127.0.0.1",
)
@click.option(
    "-p",
    "--port",
    type=int,
    help="Broker port",
    default=61613,
)
@click.option(
    "-l",
    "--log-level",
    type=str,
    help="Logger level: TRACE, DEBUG, INFO, WARNING, ERROR or CRITICAL, "
    "defaults to WARNING",
    default="WARNING",
)
@click.option(
    "-i",
    "--impl",
    type=click.Choice(['amqp', 'stomp'], case_sensitive=False),
    help="Broker implementation: 'stomp' or 'amqp', defaults to stomp",
    default='stomp'
)
@click.option(
    "-u",
    "--userid",
    type=str,
    help="Username [for AMQP client only], defaults to 'guest'",
    default="guest"
)
@click.option(
    "-w",
    "--password",
    type=str,
    help="Password [for AMQP client only], defaults to 'guest'",
    default="guest"
)
@click.option(
    "-P",
    "--prompt",
    is_flag=True,
    help="Flag [for AMQP client only]. enable prompting the user for a password"
)
@click.option(
    "-v",
    "--virtual_host",
    type=str,
    help="Virtual host [for AMQP client only], defaults to '/'",
    default='/'
)
@click.pass_context
def controller(ctx, host: str, port: int, log_level: str, impl: str,
               userid: str, password: str, prompt: bool, virtual_host: str):  # AMQP specific options  # TODO: Handle?
    # if no command is supplied, run with the options passed
    if ctx.invoked_subcommand is None:
        print("Please invoke subcommand!")
        return
    logging.basicConfig(level=log_level)
    ctx.ensure_object(dict)
    if impl == 'amqp':
        if prompt:
            password = getpass.getpass(prompt=f"AMQP Password for user {user}:")
        client = MessagingClient(AMQPMessagingTemplate.autoconfigured(
            AMQPConfig(host, port, userid, password, virtual_host))
        )
    else:
        client = StompMessagingTemplate.autoconfigured(StompConfig(host, port))
    ctx.obj["client"] = client
    client.app.connect()


@controller.command(name="plans")
@click.pass_context
def get_plans(ctx) -> None:
    client: MessagingClient = ctx.obj["client"]
    plans = client.get_plans()
    print("PLANS")
    for plan in plans.plans:
        print("\t" + plan.name)


@controller.command(name="devices")
@click.pass_context
def get_devices(ctx) -> None:
    client: MessagingClient = ctx.obj["client"]
    print(client.get_devices().devices)


@controller.command(name="run")
@click.argument("name", type=str)
@click.option("-p", "--parameters", type=str, help="Parameters as valid JSON")
@click.pass_context
def run_plan(ctx, name: str, parameters: str) -> None:
    client: MessagingClient = ctx.obj["client"]
    renderer = CliEventRenderer()
    client.run_plan(
        name,
        json.loads(parameters),
        renderer.on_worker_event,
        renderer.on_progress_event,
        timeout=120.0,
    )

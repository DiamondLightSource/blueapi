"""Server commands of the blueapi CLI, they need the server extra to run"""

from pathlib import Path

import click
from click.exceptions import ClickException
from observability_utils.tracing import setup_tracing

from blueapi.config import OTLP_EXPORT_ENABLED, ApplicationConfig


class _ServerCommand(click.Command):
    def invoke(self, ctx: click.Context):
        try:
            return super().invoke(ctx)
        except ModuleNotFoundError as e:
            raise ClickException(
                f"{e.name} is not installed, it is needed to run the server. "
                "Install it with: pip install blueapi[server]"
            ) from e


@click.command(name="schema", cls=_ServerCommand)
@click.option("-o", "--output", type=Path, help="Path to file to save the schema")
@click.option(
    "-u",
    "--update",
    type=bool,
    is_flag=True,
    help="[Development only] update the schema in the documentation",
)
def schema(output: Path | None = None, update: bool = False) -> None:
    """Generate the schema for the REST API"""
    # Only import the service functions when starting the service or generating
    # the schema, not the controller as a new FastAPI app will be started each time.
    from blueapi.service.openapi import (
        DOCS_SCHEMA_LOCATION,
        generate_schema,
        print_schema_as_yaml,
        write_schema_as_yaml,
    )

    schema = generate_schema()

    if update:
        output = DOCS_SCHEMA_LOCATION
    if output is not None:
        write_schema_as_yaml(output, schema)
    else:
        print_schema_as_yaml(schema)


@click.command(name="serve", cls=_ServerCommand)
@click.pass_obj
def start_application(obj: dict):
    """Run a worker that accepts plans to run"""
    config: ApplicationConfig = obj["config"]

    # Only import the service functions when starting the service or generating
    # the schema, not the controller as a new FastAPI app will be started each time.
    from blueapi.service.main import start

    # Set up basic automated instrumentation for the FastAPI app, creating the
    # observability context.
    setup_tracing("BlueAPI", OTLP_EXPORT_ENABLED)
    start(config)


@click.command(name="setup-scratch", cls=_ServerCommand)
@click.pass_obj
def scratch(obj: dict) -> None:
    from blueapi.service.scratch import setup_scratch

    config: ApplicationConfig = obj["config"]
    if config.scratch is not None:
        setup_scratch(config.scratch)
    else:
        raise KeyError("No scratch config supplied")


SERVER_COMMANDS = [schema, start_application, scratch]

"""The blueapi command: shared options, plus the client and the server commands.

Client and server do not import each other, this is the one place they are put together
"""

import json
import os
import stat
import textwrap
from pathlib import Path

import click
from click.exceptions import ClickException

from blueapi import __version__, config
from blueapi.config import ApplicationConfig, ConfigLoader
from blueapi.log import set_up_logging
from blueapi.service.cli import SERVER_COMMANDS


@click.group(
    invoke_without_command=True, context_settings={"auto_envvar_prefix": "BLUEAPI"}
)
@click.version_option(version=__version__, prog_name="blueapi")
@click.option(
    "-h",
    "--host",
    type=str,
    help=textwrap.dedent(
        """
        Hostname for the blueapi instance to use

        Value should be the full URL including scheme (and port if non-default),
        eg `--host http://localhost:8000`
        """
    ),
)
@click.option(
    "-c", "--config", type=Path, help="Path to configuration YAML file", multiple=True
)
@click.option(
    "-v",
    "--verbose",
    "log_level",
    flag_value="DEBUG",
    help="Include DEBUG level logging output",
)
@click.option(
    "-q",
    "--quiet",
    "log_level",
    flag_value="ERROR",
    help="Reduce logging noise to only show errors",
)
@click.pass_context
def main(
    ctx: click.Context,
    config: tuple[Path, ...],
    host: str | None = None,
    log_level: str | None = None,
) -> None:
    # if no command is supplied, run with the options passed

    # Set umask to DLS standard
    os.umask(stat.S_IWOTH)

    config_loader = ConfigLoader(ApplicationConfig)
    try:
        config_loader.use_values_from_yaml(*config)
    except FileNotFoundError as fnfe:
        raise ClickException(f"Config file not found: {fnfe.filename}") from fnfe
    if host:
        config_loader.use_values({"api": {"url": host}})
    if log_level:
        config_loader.use_values({"logging": {"level": log_level}})

    loaded_config: ApplicationConfig = config_loader.load()

    set_up_logging(loaded_config.logging)

    ctx.ensure_object(dict)
    ctx.obj["config"] = loaded_config

    if ctx.invoked_subcommand is None:
        print("Please invoke subcommand!")


@click.option(
    "-o", "--output", type=Path, help="Path to file to save the config schema"
)
@click.option(
    "-u",
    "--update",
    type=bool,
    is_flag=True,
    help="[Development only] update the config schema in the documentation",
)
@main.command(name="config-schema")
def config_schema(output: Path | None = None, update: bool = False) -> None:
    from blueapi.config import generate_config_schema

    schema = generate_config_schema()
    if update:
        output = config.CONFIG_SCHEMA_LOCATION
    if output is not None:
        with output.open("w") as stream:
            json.dump(schema, stream, indent=4)
            stream.write("\n")
    else:
        print(json.dumps(schema))


def _needs_client_extra(name: str, missing: str | None) -> click.Command:
    @click.command(name, context_settings={"ignore_unknown_options": True})
    @click.argument("args", nargs=-1, type=click.UNPROCESSED)
    def command(args: tuple[str, ...]) -> None:
        raise ClickException(
            f"{missing} is not installed, it is needed to run the client. "
            "Install it with: pip install blueapi[client]"
        )

    return command


try:
    from blueapi.cli.cli import CLIENT_COMMANDS
except ModuleNotFoundError as e:
    CLIENT_COMMANDS = [
        _needs_client_extra(name, e.name) for name in ("controller", "login", "logout")
    ]

for command in [*CLIENT_COMMANDS, *SERVER_COMMANDS]:
    main.add_command(command)

# test with: python -m blueapi
if __name__ == "__main__":
    main()

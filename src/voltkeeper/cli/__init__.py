# ABOUTME: Voltkeeper CLI entry point — root Click group and subcommand registration.

import click

from voltkeeper import __version__


@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(
    version=__version__,
    prog_name="voltkeeper",
    message="%(prog)s %(version)s",
)
@click.pass_context
def cli(ctx: click.Context):
    """Voltkeeper CLI, supporting Bluetti power station devices \u2014 scan, connect, and read data over BLE.

    \b
    Examples:
      voltkeeper status              # auto-scan and read battery data
      voltkeeper status AA:BB:CC:DD:EE:FF  # connect directly
      voltkeeper scan                # scan for nearby devices
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)


# Subcommand registration — each import attaches its commands to the 'cli' group.
# Imports must follow the cli definition so decorators can reference it.
from voltkeeper.cli import (  # noqa: E402, F401
    config,
    daemon,
    loadtest,
    mqtt,
    scan,
    services,
    status,
    verify,
    write,
)

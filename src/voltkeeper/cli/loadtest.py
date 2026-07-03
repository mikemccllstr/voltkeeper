# ABOUTME: CLI load-test command — run a battery discharge characterization test.

import asyncio
from datetime import datetime

import click

from voltkeeper import load_test
from voltkeeper.bluetooth import lookup_scan_result
from voltkeeper.cli import cli
from voltkeeper.cli._helpers import _close_loop, _device_from_scan


@cli.command("load-test")
@click.argument("address")
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    help="CSV output file (default: ac2a_load_test_YYYYMMDD_HHMMSS.csv)",
)
@click.option(
    "-i",
    "--interval",
    type=int,
    default=60,
    show_default=True,
    help="Sample interval in seconds (minimum 15).",
)
@click.option(
    "-l",
    "--expected-load",
    type=float,
    help="Known constant load in watts for analysis reference.",
)
@click.option(
    "-p",
    "--phase",
    type=str,
    help="Label for this test phase.",
)
def load_test_command(address, output, interval, expected_load, phase):
    """Run a battery discharge characterization test.

    Coaches you through setup, then logs device stats to a CSV file
    every N seconds until the battery reaches 0% or you press Ctrl-C.

    \b
    Example:
      voltkeeper load-test AA:BB:CC:DD:EE:FF -l 500 -p "500W heater on AC"
    """

    if interval < load_test.MIN_INTERVAL:
        raise click.BadParameter(f"Interval must be at least {load_test.MIN_INTERVAL} seconds.")

    address = address.upper()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        sr = loop.run_until_complete(lookup_scan_result(address))
    finally:
        loop.close()

    device = _device_from_scan(sr)

    if output is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"ac2a_load_test_{ts}.csv"

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(
            load_test.run_load_test(device, output, interval, expected_load, phase, encrypted=sr.encrypted or False)
        )
    except KeyboardInterrupt:
        click.echo("\nInterrupted.")
    except Exception as exc:
        click.secho(f"\nError: {exc}", fg="red")
    finally:
        _close_loop(loop)

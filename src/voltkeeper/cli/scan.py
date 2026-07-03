# ABOUTME: CLI scan command — discover nearby Bluetti devices via BLE.

import asyncio
import sys

import click

from voltkeeper.cli import cli
from voltkeeper.cli._helpers import _close_loop


@cli.command()
@click.option(
    "--timeout",
    "-t",
    type=float,
    default=10.0,
    show_default=True,
    help="BLE scan timeout in seconds.",
)
def scan(timeout):
    """Scan for nearby Bluetti devices and display their MAC addresses."""
    from voltkeeper.bluetooth import contribution_hint, prefix_lookup
    from voltkeeper.bluetooth import scan_devices as do_scan

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        devices = loop.run_until_complete(do_scan(timeout=timeout))
    except KeyboardInterrupt:
        click.echo("\nCancelled.")
        return
    finally:
        _close_loop(loop)

    if not devices:
        click.secho("No Bluetti devices found.", fg="red")
        click.echo("Make sure the device is powered on and in Bluetooth range.")
        sys.exit(1)

    tiers_found: set = set()
    label = click.style(str(len(devices)), fg="cyan", bold=True)
    click.echo(f"\n{label} device(s) found:\n")
    for sr in devices:
        cls = prefix_lookup(sr.name)
        tier = cls.SUPPORT_TIER if cls is not None else None
        if tier is not None:
            tiers_found.add(tier)
        click.echo(f"  {sr.display(tier=tier)}")

    hint = contribution_hint(tiers_found)
    if hint:
        click.echo()
        click.echo(hint)

    click.echo()
    if len(devices) == 1:
        click.echo("To read data from this device:")
        click.echo(f"  {click.style(f'voltkeeper status {devices[0].address}', bold=True)}")
    else:
        click.echo("To read data from a specific device:")
        for sr in devices:
            cmd = click.style(f"voltkeeper status {sr.address}", bold=True)
            click.echo(f"  {cmd}")

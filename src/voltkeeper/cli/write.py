# ABOUTME: CLI write command — write register values to a Bluetti device.

import asyncio
import sys

import click

from voltkeeper.bluetooth import lookup_scan_result
from voltkeeper.bluetooth.client import BluetoothClient
from voltkeeper.bluetooth.exc import ModbusError
from voltkeeper.cli import cli
from voltkeeper.cli._helpers import _close_loop, _device_from_scan, _discover_api_key, _resolve_daemon_url
from voltkeeper.cli.status import _field_hint


def _show_field_help(field_name: str, address: str) -> None:
    """Display type, enum values, and range for a writable field."""
    import asyncio as _asyncio

    loop = _asyncio.new_event_loop()
    _asyncio.set_event_loop(loop)
    try:
        sr = loop.run_until_complete(lookup_scan_result(address))
    finally:
        loop.close()

    device = _device_from_scan(sr)

    if not device.has_field_setter(field_name):
        click.secho(f"Unknown writable field: {field_name}", fg="red")
        click.echo(f"Available fields: {', '.join(device.WRITABLE_FIELD_NAMES)}")
        sys.exit(1)

    matches = [f for f in device.control_struct.fields if f.name == field_name]
    if not matches:
        click.echo(f"Field {field_name} is writable but has no control struct definition.")
        return

    device_field = matches[0]
    hint = _field_hint(device_field)
    if hint:
        click.echo(f"{field_name}: {hint}")
    else:
        click.echo(f"{field_name}: {type(device_field).__name__}")


@cli.command()
@click.argument("address")
@click.argument("field")
@click.argument("value")
@click.option(
    "--daemon",
    type=str,
    default=None,
    help="Send command through voltkeeperd daemon at this URL instead of BLE directly.",
)
@click.option(
    "--help-field",
    type=str,
    default=None,
    help="Show valid values and type information for a specific writable field.",
)
def write(address, field, value, daemon, help_field):
    """Write a register on a Bluetti device.

    \b
    Examples:
      voltkeeper write AA:BB:CC:DD:EE:FF ac_output on

      voltkeeper write AA:BB:CC:DD:EE:FF dc_output off

      voltkeeper write AA:BB:CC:DD:EE:FF charging_mode turbo

    \b
    Use --help-field <field> to see valid values for any writable field:
      voltkeeper write --help-field charging_mode

      voltkeeper write --help-field inv_freq
    """
    if daemon:
        _write_via_daemon(daemon, address, field, value)
        return

    address = address.upper()

    # --help-field mode: show type and valid values without connecting
    if help_field:
        _show_field_help(help_field, address)
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        sr = loop.run_until_complete(lookup_scan_result(address))
    finally:
        loop.close()

    device = _device_from_scan(sr)

    if not device.has_field_setter(field):
        click.secho(f"Unknown writable field: {field}", fg="red")
        click.echo(f"Available fields: {', '.join(device.WRITABLE_FIELD_NAMES)}")
        click.echo("Use --help-field <field> to see valid values for a specific field.")
        sys.exit(1)

    try:
        cmd = device.build_setter_command(field, value)
    except (ValueError, KeyError) as e:
        click.secho(f"Invalid value for {field}: {value} ({e})", fg="red")
        sys.exit(1)

    client = BluetoothClient(address, encrypted=sr.encrypted or False)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(client.connect())
        click.echo(f"Writing {field} = {value} ...")
        loop.run_until_complete(client.execute(cmd))
        click.secho("Done.", fg="green")
    except KeyboardInterrupt:
        click.echo("\nInterrupted.")
        sys.exit(0)
    except ModbusError as e:
        click.secho(f"Device rejected command: {e}", fg="red")
        sys.exit(1)
    except Exception as exc:
        click.secho(f"Error: {exc}", fg="red")
        sys.exit(1)
    finally:
        loop.run_until_complete(client.disconnect())
        _close_loop(loop)
        click.echo("Disconnected.")


# ── Daemon-mode write helper ──


def _write_via_daemon(raw_url: str, address: str, field: str, value: str) -> None:
    url = _resolve_daemon_url(raw_url)
    api_key = _discover_api_key()

    import json as _json
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    parsed_value = _parse_field_value(field, value)

    body = _json.dumps({"field": field, "value": parsed_value}).encode()
    req = Request(f"{url}/api/device/{address.upper()}/command", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode())
            if data.get("accepted"):
                click.echo(f"Command sent: {field} = {parsed_value}")
            else:
                click.secho(f"Command rejected: {data}", fg="yellow")
    except HTTPError as e:
        body_data = e.read().decode() if e.fp else str(e)
        click.secho(f"Error: {e.code} - {body_data}", fg="red")
    except URLError as e:
        click.secho(f"Error connecting to daemon at {url}: {e}", fg="red")


def _parse_field_value(field: str, value: str):
    lower = value.lower()
    if lower in ("on", "true"):
        return True
    if lower in ("off", "false"):
        return False
    if lower == "toggle":
        return "toggle"
    return value

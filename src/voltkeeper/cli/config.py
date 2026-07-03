# ABOUTME: CLI config commands — read and write voltkeeper daemon configuration.

import sys

import click

from voltkeeper.cli import cli
from voltkeeper.cli._helpers import _discover_api_key, _resolve_daemon_url
from voltkeeper.config import ConfigError, load_config, write_config

# Keys that can be set via `config set` and whether they require a daemon restart.
_CONFIG_SETTABLE = {
    "server.host": True,
    "server.port": True,
    "server.api_key": True,
    "server.mdns": False,
    "scan.interval": False,
    "scan.timeout": False,
}


@cli.group()
def config():
    """Read and write voltkeeper daemon configuration."""


@config.command("show")
def config_show():
    """Display the current daemon configuration."""
    from voltkeeper.config import CONFIG_SEARCH_PATHS, _find_config

    try:
        config_path = _find_config()
    except ConfigError:
        click.secho("No config file found. Searched:", fg="red")
        for p in CONFIG_SEARCH_PATHS:
            click.echo(f"  {p}")
        sys.exit(1)

    try:
        cfg = load_config(config_path)
    except ConfigError as e:
        click.secho(f"Error reading config: {e.message}", fg="red")
        sys.exit(1)
    masked_key = cfg.server.api_key[:4] + "..." if len(cfg.server.api_key) > 4 else "***"

    click.echo(f"Config file: {config_path}\n")
    click.echo(f"  server.host:        {cfg.server.host}")
    click.echo(f"  server.port:        {cfg.server.port}")
    click.echo(f"  server.api_key:     {masked_key}")
    click.echo(f"  server.mdns:        {cfg.server.mdns}")
    if cfg.server.interface:
        click.echo(f"  server.interface:   {cfg.server.interface}")
    if cfg.server.allowed_networks:
        click.echo(f"  server.allowed_networks: {cfg.server.allowed_networks}")
    click.echo(f"  scan.interval:      {cfg.scan.interval}")
    click.echo(f"  scan.timeout:       {cfg.scan.timeout}")
    click.echo(f"\n  devices ({len(cfg.devices)}):")
    for d in cfg.devices:
        name_part = f"  ({d.name})" if d.name else ""
        click.echo(f"    {d.address}{name_part}")


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.option("--daemon-url", default=None, help="Daemon URL for reload (default: http://localhost:8080).")
def config_set(key, value, daemon_url):
    """Set a configuration value.

    \b
    Settable keys:
      server.host, server.port, server.api_key, server.mdns
      scan.interval, scan.timeout
    """
    from voltkeeper.config import find_writable_config_path

    if key not in _CONFIG_SETTABLE:
        click.secho(f"Unknown key: {key}", fg="red")
        click.echo("Valid keys: " + ", ".join(sorted(_CONFIG_SETTABLE)))
        sys.exit(1)

    config_path = find_writable_config_path()
    if config_path.exists():
        try:
            cfg = load_config(config_path)
        except ConfigError as e:
            click.secho(f"Error reading config: {e.message}", fg="red")
            sys.exit(1)
    else:
        click.secho(f"No config file found; creating {config_path}", fg="yellow")
        from voltkeeper.config import Config, ServerConfig

        cfg = Config(server=ServerConfig(api_key=""))

    # Apply the value
    from voltkeeper.config import ScanConfig
    from voltkeeper.config import ServerConfig as _SC

    section, field = key.split(".", 1)
    try:
        section_obj: _SC | ScanConfig = cfg.server if section == "server" else cfg.scan
        current = getattr(section_obj, field)
        # bool must be checked before int since bool is a subclass of int
        if isinstance(current, bool):
            coerced: object = value.lower() in ("true", "yes", "1", "on")
        elif isinstance(current, int):
            coerced = int(value)
        elif isinstance(current, float):
            coerced = float(value)
        else:
            coerced = value
        setattr(section_obj, field, coerced)
    except (ValueError, AttributeError) as e:
        click.secho(f"Invalid value for {key}: {e}", fg="red")
        sys.exit(1)

    write_config(cfg, config_path)
    click.echo(f"Set {key} = {value}")

    restart_required = _CONFIG_SETTABLE[key]
    _try_reload_daemon(daemon_url, restart_required, key)


@config.command("add-device")
@click.argument("address")
@click.option("--name", default=None, help="Human-readable device name.")
@click.option("--daemon-url", default=None, help="Daemon URL for reload.")
def config_add_device(address, name, daemon_url):
    """Add a device to the daemon configuration."""
    from voltkeeper.config import DeviceEntry, find_writable_config_path

    address = address.upper()
    config_path = find_writable_config_path()
    if config_path.exists():
        try:
            cfg = load_config(config_path)
        except ConfigError as e:
            click.secho(f"Error reading config: {e.message}", fg="red")
            sys.exit(1)
    else:
        from voltkeeper.config import Config, ServerConfig

        cfg = Config(server=ServerConfig(api_key=""))

    if any(d.address == address for d in cfg.devices):
        click.echo(f"Device {address} is already in config.")
        return

    cfg.devices.append(DeviceEntry(address=address, name=name))
    write_config(cfg, config_path)
    name_part = f" ({name})" if name else ""
    click.secho(f"Added device {address}{name_part}.", fg="green")
    _try_reload_daemon(daemon_url, False, "devices")


@config.command("remove-device")
@click.argument("address")
@click.option("--daemon-url", default=None, help="Daemon URL for reload.")
def config_remove_device(address, daemon_url):
    """Remove a device from the daemon configuration."""
    from voltkeeper.config import find_writable_config_path

    address = address.upper()
    config_path = find_writable_config_path()
    if not config_path.exists():
        click.echo(f"Device {address} not found in config (no config file).")
        return

    try:
        cfg = load_config(config_path)
    except ConfigError as e:
        click.secho(f"Error reading config: {e.message}", fg="red")
        sys.exit(1)
    before = len(cfg.devices)
    cfg.devices = [d for d in cfg.devices if d.address != address]
    if len(cfg.devices) == before:
        click.echo(f"Device {address} not found in config.")
        return

    write_config(cfg, config_path)
    click.secho(f"Removed device {address}.", fg="green")
    _try_reload_daemon(daemon_url, False, "devices")


def _try_reload_daemon(daemon_url: str | None, restart_required: bool, changed_key: str) -> None:
    """Attempt to reload the running daemon; print status of the result."""
    import json as _json
    from urllib.error import URLError
    from urllib.request import Request, urlopen

    if restart_required:
        click.echo(f"Restart required: {changed_key} change takes effect after daemon restart.")
        return

    url = _resolve_daemon_url(daemon_url or "localhost")
    api_key = _discover_api_key()

    req = Request(f"{url}/api/reload", data=b"", method="POST")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urlopen(req, timeout=3) as resp:
            data = _json.loads(resp.read().decode())
            if data.get("reloaded"):
                click.echo("Config reloaded successfully.")
            elif data.get("restart_required"):
                click.echo(f"Restart required: {data.get('reason', '')}")
    except URLError:
        click.echo("Config written. Start or restart the daemon to apply.")

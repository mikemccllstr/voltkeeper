# ABOUTME: CLI daemon commands — manage the voltkeeperd daemon process.

import json
import shutil
import sys

import click

from voltkeeper.cli import cli
from voltkeeper.cli._helpers import _discover_api_key, _resolve_daemon_url
from voltkeeper.config import ConfigError, load_config, write_config


@cli.group()
def daemon():
    """Manage the voltkeeperd daemon process."""


@daemon.command("start")
def daemon_start():
    """Start the voltkeeperd daemon.

    Run voltkeeperd in the foreground. For production use, set up
    a systemd service unit.
    """
    from voltkeeper.daemon import main as daemon_main

    click.echo("Starting voltkeeperd...")
    daemon_main()


@daemon.command("status")
@click.option(
    "--daemon-url",
    type=str,
    default=None,
    help="URL of the running daemon (default: http://localhost:8080).",
)
def daemon_status(daemon_url):
    """Show status of the voltkeeperd daemon and connected devices."""
    url = _resolve_daemon_url(daemon_url or "localhost")

    from urllib.error import URLError
    from urllib.request import Request, urlopen

    api_key = _discover_api_key()

    req = Request(f"{url}/api/devices")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urlopen(req, timeout=5) as resp:
            if resp.status == 401:
                click.secho("Error: Unauthorized. Check API key in voltkeeperd config.", fg="red")
                return
            data = json.loads(resp.read().decode())
    except URLError as e:
        click.secho(f"Error: Could not connect to daemon at {url}: {e}", fg="red")
        return
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")
        return

    if not data:
        click.echo("Daemon is running but no devices are configured or in range.")
        return

    label = click.style(str(len(data)), fg="cyan", bold=True)
    click.echo(f"\n{label} device(s):\n")
    for d in data:
        soc = d.get("summary", {}).get("soc", "--")
        status_color = {"online": "green", "missing": "yellow", "new": "blue"}.get(d["status"], "white")
        line = f"  [{click.style(d['status'].upper(), fg=status_color)}] {d['address']}"
        if d.get("name"):
            line += f"  {d['name']}"
        if d.get("type"):
            line += f"  ({d['type']})"
        if soc != "--":
            line += f"  SOC: {round(soc)}%"
        click.echo(line)
    click.echo()


@daemon.command("stop")
@click.option(
    "--daemon-url",
    type=str,
    default=None,
    help="URL of the running daemon (default: http://localhost:8080).",
)
def daemon_stop(daemon_url):
    """Stop the running voltkeeperd daemon."""
    import subprocess
    from pathlib import Path
    from urllib.error import URLError
    from urllib.request import Request, urlopen

    unit_file = Path.home() / ".config" / "systemd" / "user" / "voltkeeper.service"

    if unit_file.exists():
        click.echo("Stopping voltkeeper user service via systemctl...")
        result = subprocess.run(
            ["systemctl", "--user", "stop", "voltkeeper"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            click.secho("voltkeeper service stopped.", fg="green")
        else:
            click.secho(f"systemctl stop failed: {result.stderr.strip()}", fg="red")
            sys.exit(1)
        return

    url = _resolve_daemon_url(daemon_url or "localhost")
    api_key = _discover_api_key()
    click.echo(f"Sending shutdown request to {url}...")

    req = Request(f"{url}/api/shutdown", data=b"", method="POST")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urlopen(req, timeout=5) as resp:
            if resp.status == 202:
                click.secho("Daemon is shutting down.", fg="green")
            elif resp.status == 401:
                click.secho("Unauthorized — check API key in config.", fg="red")
                sys.exit(1)
            else:
                click.secho(f"Unexpected response: {resp.status}", fg="yellow")
    except URLError as e:
        click.secho(f"Could not reach daemon at {url}: {e}", fg="red")
        click.echo("If running in the foreground, press Ctrl+C to stop it.")
        sys.exit(1)


@daemon.command("install")
@click.option("--lan", is_flag=True, default=False, help="Bind on all interfaces and advertise via mDNS.")
def daemon_install(lan):
    """Install voltkeeperd as a user-level systemd service.

    Generates a config file with a fresh API key and writes a hardened
    systemd unit file, then enables and starts the service. Safe to run
    again — if already installed, prints current status and exits.
    """
    import secrets
    import subprocess
    from pathlib import Path

    from voltkeeper.config import Config, ServerConfig, find_writable_config_path

    unit_file = Path.home() / ".config" / "systemd" / "user" / "voltkeeper.service"

    if unit_file.exists():
        click.echo("voltkeeper is already installed as a user systemd service.")
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "voltkeeper"],
            capture_output=True,
            text=True,
        )
        status = result.stdout.strip() or "unknown"
        click.echo(f"  Service status:  {status}")
        config_path = find_writable_config_path()
        click.echo(f"  Config:          {config_path}")
        click.echo("  URL:             http://localhost:8080")
        click.echo("  Logs:            journalctl --user -u voltkeeper -f")
        return

    voltkeeperd = shutil.which("voltkeeperd")
    if not voltkeeperd:
        click.secho("Error: voltkeeperd binary not found in PATH.", fg="red")
        click.echo("Install voltkeeper first: pip install voltkeeper")
        sys.exit(1)

    try:
        cfg = load_config()
    except ConfigError:
        api_key = secrets.token_urlsafe(32)
        host = "0.0.0.0" if lan else "127.0.0.1"
        cfg = Config(server=ServerConfig(api_key=api_key, host=host, port=8080, mdns=lan), devices=[])
    else:
        if lan:
            cfg.server.host = "0.0.0.0"
            cfg.server.mdns = True

    config_path = find_writable_config_path()
    write_config(cfg, config_path)
    click.echo(f"  Wrote config:    {config_path}")

    unit_file.parent.mkdir(parents=True, exist_ok=True)
    unit_file.write_text(_make_unit_file(voltkeeperd))
    click.echo(f"  Wrote unit file: {unit_file}")

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    click.echo("  Ran: systemctl --user daemon-reload")
    subprocess.run(["systemctl", "--user", "enable", "voltkeeper"], check=True)
    click.echo("  Ran: systemctl --user enable voltkeeper")
    subprocess.run(["systemctl", "--user", "start", "voltkeeper"], check=True)
    click.echo("  Ran: systemctl --user start voltkeeper")

    click.echo()
    click.secho("voltkeeper installed and started.", fg="green")
    click.echo(f"  Config: {config_path}")
    click.echo("  URL:    http://localhost:8080")
    click.echo("  Logs:   journalctl --user -u voltkeeper -f")

    if lan:
        click.echo()
        click.secho("LAN mode — keep your API key secret:", fg="yellow")
        click.echo(f"  API key: {cfg.server.api_key}")
        click.echo("  Anyone on your LAN can use this key to control your devices.")


@daemon.command("uninstall")
def daemon_uninstall():
    """Uninstall the voltkeeperd systemd user service.

    Stops and disables the service, removes the unit file, and reloads
    systemd. Does not remove the config file or data.
    """
    import subprocess
    from pathlib import Path

    unit_file = Path.home() / ".config" / "systemd" / "user" / "voltkeeper.service"

    if not unit_file.exists():
        click.echo("voltkeeper is not installed as a user systemd service.")
        return

    if not click.confirm("Uninstall voltkeeper systemd service?"):
        click.echo("Aborted.")
        return

    subprocess.run(["systemctl", "--user", "stop", "voltkeeper"], capture_output=True)
    click.echo("  Ran: systemctl --user stop voltkeeper")
    subprocess.run(["systemctl", "--user", "disable", "voltkeeper"], capture_output=True)
    click.echo("  Ran: systemctl --user disable voltkeeper")
    unit_file.unlink()
    click.echo(f"  Removed: {unit_file}")
    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
    click.echo("  Ran: systemctl --user daemon-reload")

    click.echo()
    click.secho("voltkeeper service uninstalled.", fg="green")
    click.echo("Config and data files were not removed.")


def _make_unit_file(exec_start: str) -> str:
    return f"""\
[Unit]
Description=Voltkeeper daemon — Bluetti device manager
After=bluetooth.target
Wants=bluetooth.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=on-failure
RestartSec=30
Environment=PYTHONUNBUFFERED=1
PrivateTmp=true
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=%h/.config/voltkeeper
RestrictAddressFamilies=AF_INET AF_INET6 AF_BLUETOOTH AF_UNIX
SystemCallFilter=@system-service
SystemCallArchitectures=native
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_RAW
MemoryMax=256M
TasksMax=64

[Install]
WantedBy=default.target
"""

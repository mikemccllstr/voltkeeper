# ABOUTME: CLI MQTT commands — publish device state to an MQTT broker and listen for shutdown triggers.

import asyncio

import click

from voltkeeper.bluetooth import ScanResult, build_device, device_registry, is_supported_device_type, lookup_scan_result
from voltkeeper.cli import cli
from voltkeeper.cli._helpers import _close_loop, _device_from_scan


@cli.command("mqtt-publish")
@click.argument("address")
@click.option(
    "--serial",
    help="Device serial number (overrides BLE lookup for MQTT topic).",
)
@click.option(
    "--broker",
    required=True,
    help="MQTT broker hostname or IP address.",
)
@click.option(
    "--port",
    type=int,
    default=1883,
    show_default=True,
    help="MQTT broker port.",
)
@click.option(
    "--username",
    default=None,
    help="MQTT broker username.",
)
@click.option(
    "--password",
    default=None,
    help="MQTT broker password.",
)
@click.option(
    "--interval",
    type=int,
    default=0,
    show_default=True,
    help="Seconds between polling cycles (0 = as fast as possible).",
)
@click.option(
    "--ha-config",
    type=click.Choice(["normal", "none", "advanced"]),
    default="normal",
    show_default=True,
    help="Home Assistant MQTT discovery mode.",
)
@click.option(
    "--restart-on-source-change/--no-restart-on-source-change",
    default=False,
    show_default=True,
    help="Exit cleanly when source code changes, so systemd restarts the process.",
)
def mqtt_publish(address, serial, broker, port, username, password, interval, ha_config, restart_on_source_change):
    """Publish device state to an MQTT broker.

    Continuously polls the device over BLE and publishes state to MQTT.
    Supports Home Assistant MQTT auto-discovery (on by default).

    \b
    Example:
      voltkeeper mqtt-publish AA:BB:CC:DD:EE:FF --broker 192.168.1.100
    """
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    from voltkeeper.bus import EventBus
    from voltkeeper.device_handler import DeviceHandler, SourceChangeWatcher, _watch_source_changes
    from voltkeeper.mqtt_client import MQTTClient

    address = address.upper()

    if serial:
        device = build_device(address, address)
        device.sn = serial
    else:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            sr = loop.run_until_complete(lookup_scan_result(address, timeout=1.0))
        except Exception:
            sr = ScanResult(address=address, name=address, encrypted=None)
        finally:
            loop.close()
        device = _device_from_scan(sr)
    bus = EventBus()
    handler = DeviceHandler(address, device, interval, bus, encrypted=sr.encrypted or False)
    mqtt_client = MQTTClient(
        bus=bus,
        hostname=broker,
        port=port,
        username=username,
        password=password,
        home_assistant_mode=ha_config,
    )

    watcher = None
    if restart_on_source_change:
        from pathlib import Path

        watcher = SourceChangeWatcher(Path(__file__).resolve().parent)
        watcher.start()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:

        async def run_bridge():
            tasks = [bus.run(), handler.run(), mqtt_client.run()]
            if watcher:
                tasks.append(_watch_source_changes(watcher))
            await asyncio.gather(*tasks)

        click.echo(f"Starting MQTT bridge for {address} → {broker}:{port}")
        loop.run_until_complete(run_bridge())
    except KeyboardInterrupt:
        click.echo("\nShutting down...")
    finally:
        if watcher:
            watcher.stop()
        _close_loop(loop)
        click.echo("Stopped.")


@cli.command("mqtt-listen")
@click.argument("address", required=False)
@click.option(
    "--serial",
    help="Device serial number (required if ADDRESS not given).",
)
@click.option(
    "--device-type",
    type=str,
    default=None,
    help="Device model (e.g. AC2A). Required when --serial is given without ADDRESS.",
)
@click.option("--broker", required=True, help="MQTT broker hostname.")
@click.option("--port", type=int, default=1883, show_default=True, help="MQTT broker port.")
@click.option("--username", help="MQTT broker username.")
@click.option("--password", help="MQTT broker password (visible in service file).")
@click.option(
    "--shutdown-at",
    type=int,
    default=10,
    show_default=True,
    help="SOC %% threshold for initiating shutdown.",
)
@click.option(
    "--grace-period",
    type=int,
    default=60,
    show_default=True,
    help="Seconds below threshold before shutdown triggers.",
)
@click.option(
    "--restart-on-source-change/--no-restart-on-source-change",
    default=False,
    show_default=True,
    help="Exit cleanly when source code changes, so systemd restarts the process.",
)
def mqtt_listen(
    address,
    serial,
    device_type,
    broker,
    port,
    username,
    password,
    shutdown_at,
    grace_period,
    restart_on_source_change,
):
    """Watch battery SOC via MQTT and trigger system shutdown.

    Subscribes to the device's MQTT topic and watches total_battery_percent.
    When SOC drops below --shutdown-at and stays there for --grace-period
    seconds, runs 'sudo shutdown -h now'.

    \b
    Examples:
      voltkeeper mqtt-listen --serial 2409000123456 --broker 192.168.1.100
      voltkeeper mqtt-listen AA:BB:CC:DD:EE:FF --broker 192.168.1.100
    """
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    from voltkeeper.device_handler import SourceChangeWatcher, _watch_source_changes
    from voltkeeper.shutdown_watch import _is_shutdown_supported, run_shutdown_listener

    if not _is_shutdown_supported():
        raise click.ClickException("System shutdown via mqtt-listen is only supported on Linux")

    if not address and not serial:
        raise click.UsageError("Provide ADDRESS, --serial, or both.")

    if address:
        address = address.upper()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            sr = loop.run_until_complete(lookup_scan_result(address))
        finally:
            loop.close()
        _device = _device_from_scan(sr)
        sn = _device.sn
        device_type_resolved = _device.type
    elif device_type:
        if not is_supported_device_type(device_type):
            raise click.BadParameter(
                f"Unknown device type {device_type!r}. Known: {sorted(device_registry())}",
                param_hint="--device-type",
            )
        device_type_resolved = device_type
        sn = serial
    else:
        raise click.UsageError(
            "When ADDRESS is omitted, pass --device-type so the MQTT topic is correct (e.g. --device-type AC2A)."
        )

    topic = f"bluetti/state/{device_type_resolved}-{sn}/total_battery_percent"

    watcher = None
    if restart_on_source_change:
        from pathlib import Path

        watcher = SourceChangeWatcher(Path(__file__).resolve().parent)
        watcher.start()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:

        async def run():
            tasks = [
                run_shutdown_listener(topic, broker, port, username, password, shutdown_at, grace_period),
            ]
            if watcher:
                tasks.append(_watch_source_changes(watcher))
            await asyncio.gather(*tasks)

        loop.run_until_complete(run())
    except KeyboardInterrupt:
        click.echo("\nShutting down...")
    finally:
        if watcher:
            watcher.stop()
        _close_loop(loop)
        click.echo("Stopped.")

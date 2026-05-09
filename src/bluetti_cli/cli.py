# ABOUTME: Click CLI for Bluetti power stations — scan, status, verbose status. Uses layered architecture.

import asyncio
import os
import pwd
import shutil
import sys

import click

from . import load_test
from .bluetooth import (
    build_device,
    device_registry,
    is_supported_device_type,
    lookup_device_name,
    pick_address_after_scan,
)
from .bluetooth.client import BluetoothClient
from .bluetooth.exc import BadConnectionError, ModbusError, ParseError
from .core.commands import ReadHoldingRegisters

SERVICE_UUID = "0000ff00-0000-1000-8000-00805f9b34fb"


def _close_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Cancel pending tasks and cleanly close an event loop."""
    try:
        tasks = asyncio.all_tasks(loop)
        for task in tasks:
            task.cancel()
        if tasks:
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
    finally:
        loop.close()


# ═══════════════════════════════════════════════════════════════════════
#  CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════


@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(
    version="0.1.0",
    prog_name="bluetti-cli",
    message="%(prog)s %(version)s",
)
@click.pass_context
def cli(ctx: click.Context):
    """Bluetti power station CLI \u2014 scan, connect, and read data over BLE.

    \b
    Examples:
      bluetti-cli status              # auto-scan and read battery data
      bluetti-cli status AA:BB:CC:DD:EE:FF  # connect directly
      bluetti-cli scan                # scan for nearby devices
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)


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
    from .bluetooth import scan_devices as do_scan

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

    label = click.style(str(len(devices)), fg="cyan", bold=True)
    click.echo(f"\n{label} device(s) found:\n")
    for sr in devices:
        click.echo(f"  {sr.display()}")

    click.echo()
    if len(devices) == 1:
        click.echo("To read data from this device:")
        click.echo(f"  {click.style(f'bluetti-cli status {devices[0].address}', bold=True)}")
    else:
        click.echo("To read data from a specific device:")
        for sr in devices:
            cmd = click.style(f"bluetti-cli status {sr.address}", bold=True)
            click.echo(f"  {cmd}")


@cli.command()
@click.argument("address", required=False, default=None)
@click.option(
    "--timeout",
    "-t",
    type=float,
    default=10.0,
    show_default=True,
    help="BLE scan timeout in seconds (only used when ADDRESS is not provided).",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Display all available device information (power meters, energy totals, "
    "PV strings, grid, loads, temperatures, software versions, etc.).",
)
def status(address, timeout, verbose):
    """Read battery SOC and pack data from a Bluetti device.

    If ADDRESS is not provided, scans for nearby Bluetti devices and
    lets you pick one interactively.
    """
    if not address:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            address, device_name = loop.run_until_complete(pick_address_after_scan())
        finally:
            loop.close()
        tip = click.style(f"bluetti-cli status {address}", bold=True)
        click.echo(f"\nTip: next time, run directly with:\n  {tip}")
    else:
        address = address.upper()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            device_name = loop.run_until_complete(lookup_device_name(address))
        finally:
            loop.close()

    device = build_device(address, device_name)
    client = BluetoothClient(address)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    home = None
    inv_base = {}
    pv = {}
    grid = {}
    load = {}
    inv_info = {}
    controls = {}
    try:
        loop.run_until_complete(client.connect())

        if verbose:
            for cmd_obj in device.polling_commands:
                raw = loop.run_until_complete(client.execute(cmd_obj))
                parsed = device.parse(cmd_obj.starting_address, raw)
                if cmd_obj.starting_address >= 1100 and cmd_obj.starting_address < 1200:
                    inv_base = parsed
                elif cmd_obj.starting_address >= 1200 and cmd_obj.starting_address < 1300:
                    pv = parsed
                elif cmd_obj.starting_address >= 1300 and cmd_obj.starting_address < 1400:
                    grid = parsed
                elif cmd_obj.starting_address >= 1400 and cmd_obj.starting_address < 1500:
                    load = parsed
                elif cmd_obj.starting_address >= 1500 and cmd_obj.starting_address < 1600:
                    inv_info = parsed
                else:
                    home = parsed

            for cmd_obj in device.control_commands:
                try:
                    raw = loop.run_until_complete(client.execute(cmd_obj))
                    controls.update(device.parse(cmd_obj.starting_address, raw))
                except ModbusError:
                    # Control registers (2000+) are write-only on some models;
                    # read attempts return Modbus exceptions — expected.
                    pass
                except (ParseError, BadConnectionError) as exc:
                    click.secho(f"  ⚠  control read at {cmd_obj.starting_address} failed: {exc}", fg="yellow")
        else:
            cmd = ReadHoldingRegisters(100, 6)
            raw = loop.run_until_complete(client.execute(cmd))
            home = device.parse(100, raw)
            pwr_cmd = ReadHoldingRegisters(140, 10)
            pwr_raw = loop.run_until_complete(client.execute(pwr_cmd))
            home.update(device.parse(140, pwr_raw))

    except KeyboardInterrupt:
        click.echo("\nInterrupted.")
        sys.exit(0)
    except Exception as exc:
        click.secho(f"\nError: {exc}", fg="red")
        sys.exit(1)
    finally:
        loop.run_until_complete(client.disconnect())
        _close_loop(loop)
        click.echo("Disconnected.")

    if home is None:
        click.secho("No data received.", fg="red")
        sys.exit(1)

    if verbose:
        _print_verbose(device, home, inv_base, pv, grid, load, inv_info, controls)
    else:
        _print_status(home)


# ═══════════════════════════════════════════════════════════════════════
#  Output Formatting
# ═══════════════════════════════════════════════════════════════════════


def _print_status(home: dict) -> None:
    sep = "\u2500" * 44
    click.echo(sep)
    click.echo(f"  Battery SOC:       {home['packTotalSoc']:>5.0f} %")
    click.echo(f"  Pack Voltage:      {home['packTotalVoltage']:>5.1f} V")
    status_map = {0: "Idle", 1: "Charging", 2: "Discharging", 3: "Floating"}
    cs = home.get("packChargingStatus", 0)
    click.echo(f"  Charging Status:   {status_map.get(cs, str(cs))} ({cs})")
    if cs == 1:
        click.echo(f"  Time to Full:      {home.get('packChgFullTime', 0) * 6:>5.0f} min")
    else:
        click.echo(f"  Time to Empty:     {home.get('packDsgEmptyTime', 0) * 6:>5.0f} min")
    dc_load = home.get("totalDCPower", 0)
    ac_load = abs(home.get("totalACPower", 0))
    total_load = dc_load + ac_load
    if total_load > 0:
        click.echo(f"  DC Load:           {dc_load:>5.0f} W")
        click.echo(f"  AC Load:           {ac_load:>5.0f} W")
        click.echo(f"  Total Load:        {total_load:>5.0f} W")
    click.echo(sep)


def _print_verbose(
    device,
    home: dict,
    inv_base: dict,
    pv: dict,
    grid: dict,
    load: dict,
    inv_info: dict,
    controls: dict | None = None,
) -> None:
    sep = "\u2500" * 56
    click.echo(sep)
    click.echo(click.style("  BLUETTI DEVICE \u2014 FULL STATUS", bold=True))
    click.echo(sep)

    # ── Device Identity ──
    if home.get("deviceModel") or home.get("deviceSN"):
        click.echo(f"\n  Model:       {home.get('deviceModel', '?')}")
        click.echo(f"  Serial:      {home.get('deviceSN', '?')}")
    if inv_base.get("invType"):
        click.echo(f"  Inv Type:    {inv_base['invType']}")
    if inv_base.get("invSN"):
        click.echo(f"  Inv SN:      {inv_base['invSN']}")
    if home.get("invNumber", 0) > 0:
        click.echo(f"  Inverters:   {home['invNumber']}")
    if home.get("packCnts", 0) > 0:
        click.echo(f"  Packs:       {home['packCnts']}")

    # ── Battery ──
    click.echo(f"\n  {click.style('BATTERY', bold=True, fg='green')}")
    click.echo(f"    SOC:                  {home['packTotalSoc']:>5.0f} %")
    click.echo(f"    Voltage:              {home['packTotalVoltage']:>5.1f} V")
    click.echo(f"    Current:              {home['packTotalCurrent']:>5.1f} A")
    status_map = {0: "Idle", 1: "Charging", 2: "Discharging", 3: "Floating"}
    cs = home.get("packChargingStatus", 0)
    click.echo(f"    Status:               {status_map.get(cs, str(cs))} ({cs})")
    if cs == 1:
        click.echo(f"    Time to Full:         {home.get('packChgFullTime', 0) * 6:>5.0f} min")
    else:
        click.echo(f"    Time to Empty:        {home.get('packDsgEmptyTime', 0) * 6:>5.0f} min")
    if "packDsgEnergyTotal" in home:
        click.echo(f"    Total Discharged:     {home['packDsgEnergyTotal']:>8.1f} Wh")

    # ── Power Meters ──
    if any(k in home for k in ("totalPVPower", "totalACPower", "totalDCPower")):
        click.echo(f"\n  {click.style('POWER (instantaneous)', bold=True, fg='cyan')}")
        if "totalPVPower" in home:
            click.echo(f"    PV Input:             {home['totalPVPower']:>5.0f} W")
        if "totalACPower" in home:
            ac = home["totalACPower"]
            click.echo(f"    AC:                   {ac:>+6.0f} W  (neg=export)")
        if "totalDCPower" in home:
            click.echo(f"    DC Load:              {home['totalDCPower']:>5.0f} W")
        if "totalGridPower" in home:
            click.echo(f"    Grid:                 {home['totalGridPower']:>+6.0f} W")
        if "pvToAcPower" in home:
            click.echo(f"    PV\u2192AC:                {home['pvToAcPower']:>5.0f} W")

    # ── Energy Totals ──
    if any(k in home for k in ("totalPVChargingEnergy", "totalDCEnergy")):
        click.echo(f"\n  {click.style('ENERGY (lifetime)', bold=True, fg='yellow')}")
        if "totalPVChargingEnergy" in home:
            click.echo(f"    PV Charging:          {home['totalPVChargingEnergy']:>8.1f} Wh")
        if "totalGridChargingEnergy" in home:
            click.echo(f"    Grid Charging:        {home['totalGridChargingEnergy']:>8.1f} Wh")
        if "totalFeedbackEnergy" in home:
            click.echo(f"    Feed-back:            {home['totalFeedbackEnergy']:>8.1f} Wh")
        if "totalDCEnergy" in home:
            click.echo(f"    DC Output:            {home['totalDCEnergy']:>8.1f} Wh")
        if "totalACEnergy" in home:
            click.echo(f"    AC Output:            {home['totalACEnergy']:>8.1f} Wh")
        if "pvToAcEnergy" in home:
            click.echo(f"    PV\u2192AC:                {home['pvToAcEnergy']:>8.1f} Wh")

    # ── Temperatures ──
    if inv_base:
        temps = []
        for key, label in [
            ("ambientTemp", "Ambient"),
            ("invMaxTemp", "Inv.Max"),
            ("pvDcdcMaxTemp", "PV DCDC Max"),
        ]:
            val = inv_base.get(key)
            if val is not None:
                temps.append(f"{label}={val}\u00b0C")
        if temps:
            click.echo(f"\n  {click.style('TEMPERATURES', bold=True, fg='red')}")
            for t in temps:
                click.echo(f"    {t}")

    # ── Software Versions ──
    soft_keys = [k for k in inv_base if k.startswith("software[")]
    if soft_keys:
        click.echo(f"\n  {click.style('SOFTWARE VERSIONS', bold=True, fg='magenta')}")
        for k in sorted(soft_keys):
            click.echo(f"    {k}: {inv_base[k]}")

    # ── PV Details ──
    pv_keys = [k for k in pv if k.startswith("pv[") and k.endswith(".type") and pv.get(k, 0) != 0]
    if pv_keys:
        click.echo(f"\n  {click.style('PV STRINGS', bold=True, fg='cyan')}")
        for pk in sorted(set(k.split(".")[0] for k in pv_keys)):
            pv_type = pv.get(f"{pk}.type", "?")
            pv_status = pv.get(f"{pk}.workingStatus", "?")
            pv_power = pv.get(f"{pk}.inputPower", 0)
            pv_volt = pv.get(f"{pk}.inputVoltage", 0)
            pv_curr = pv.get(f"{pk}.inputCurrent", 0)
            click.echo(
                f"    {pk}: Power={pv_power}W  V={pv_volt:.1f}V  I={pv_curr:.1f}A  Status={pv_status}  Type={pv_type}"
            )

    # ── Grid ──
    if grid:
        click.echo(f"\n  {click.style('GRID', bold=True, fg='blue')}")
        if "frequency" in grid:
            click.echo(f"    Frequency:            {grid['frequency']:.1f} Hz")
        if "totalChgPower" in grid:
            click.echo(f"    Import Power:         {grid['totalChgPower']:>+6.0f} W")
        for i in range(3):
            pk = f"gridPhase[{i}]"
            if f"{pk}.voltage" in grid:
                click.echo(
                    f"    Phase {i + 1}:  V={grid[f'{pk}.voltage']:.1f}V  "
                    f"I={grid[f'{pk}.current']:.1f}A  P={grid[f'{pk}.power']}W"
                )

    # ── Load ──
    if load:
        click.echo(f"\n  {click.style('LOADS', bold=True, fg='blue')}")
        dc_parts = []
        for v in ("5V", "12V", "24V"):
            if f"dc{v}Power" in load:
                dc_parts.append(f"DC{v}={load[f'dc{v}Power']}W/{load[f'dc{v}Current']:.1f}A")
        if dc_parts:
            click.echo(f"    {'  '.join(dc_parts)}")
        if "dcLoadTotalPower" in load:
            click.echo(
                f"    DC Total:             {load['dcLoadTotalPower']}W  "
                f"({load.get('dcVoltTotal', 0):.1f}V / {load.get('dcCurrentTotal', 0):.1f}A)"
            )
        if "acLoadTotalPower" in load:
            click.echo(f"    AC Total:             {load['acLoadTotalPower']}W")
        for i in range(3):
            pk = f"acPhase[{i}]"
            if f"{pk}.voltage" in load:
                click.echo(
                    f"    Phase {i + 1}:  V={load[f'{pk}.voltage']:.1f}V  "
                    f"I={load[f'{pk}.current']:.1f}A  P={load[f'{pk}.power']}W"
                )

    # ── Inverter Output ──
    if inv_info:
        click.echo(f"\n  {click.style('INVERTER OUTPUT', bold=True, fg='yellow')}")
        if "frequency" in inv_info:
            click.echo(f"    Frequency:            {inv_info['frequency']:.1f} Hz")
        for i in range(3):
            pk = f"invPhase[{i}]"
            if f"{pk}.voltage" in inv_info:
                ws = inv_info.get(f"{pk}.workStatus", "?")
                click.echo(
                    f"    Phase {i + 1}:  V={inv_info[f'{pk}.voltage']:.1f}V  "
                    f"I={inv_info[f'{pk}.current']:.1f}A  "
                    f"P={inv_info[f'{pk}.power']}W  Status={ws}"
                )

    # ── Misc ──
    misc_parts = []
    if "chargingMode" in home:
        mode_map = {0: "Standard", 1: "Turbo", 2: "Silent"}
        misc_parts.append(f"Charge Mode={mode_map.get(home['chargingMode'], str(home['chargingMode']))}")
    if home.get("invWorkingStatus", 0):
        misc_parts.append(f"Inv Status={home['invWorkingStatus']}")
    if home.get("packAgingInfo", 0):
        misc_parts.append(f"Pack Aging={home['packAgingInfo']}")
    if home.get("gridParallelSoC", 0):
        misc_parts.append(f"Grid Parallel SoC={home['gridParallelSoC']}%")
    if home.get("rateVoltage") or home.get("rateFrequency"):
        misc_parts.append(f"Rated={home.get('rateVoltage', '?')}V/{home.get('rateFrequency', '?')}Hz")
    if "selfSufficiencyRate" in home:
        misc_parts.append(f"Self-Sufficiency={home['selfSufficiencyRate']}%")
    if "pvToAcEnergy" in home:
        misc_parts.append(f"PV\u2192AC Energy={home['pvToAcEnergy']:.1f}Wh")
    if misc_parts:
        click.echo(f"\n  {click.style('MISC', bold=True)}")
        for p in misc_parts:
            click.echo(f"    {p}")

    # ── Rated Currents (inverter base info) ──
    current_fields = [k for k in inv_base if "RateCurrent" in k and inv_base.get(k, 0)]
    if current_fields:
        click.echo(f"\n  {click.style('RATED CURRENTS (A)', bold=True)}")
        for k in sorted(current_fields):
            click.echo(f"    {k}: {inv_base[k] / 10.0:.1f}A")

    # ── Controls (writable fields) ──
    if controls:
        click.echo(f"\n  {click.style('CONTROLS (writable)', bold=True, fg='cyan')}")
        for name, val in sorted(controls.items()):
            if name == "ctrl_event":
                continue
            if isinstance(val, bool):
                display = "on" if val else "off"
            elif hasattr(val, "name"):
                display = val.name.lower()
            else:
                display = str(val)
            click.echo(f"    {name:<20s}  {display}")

        ctrl_event = home.get("ctrl_event") or (controls or {}).get("ctrl_event")
        if ctrl_event is not None:
            caps = device.decode_ctrl_event(ctrl_event)
            if caps is None:
                click.echo(
                    f"\n  {click.style(f'CTRL_EVENT (register 124: {ctrl_event:#018b})', bold=True, fg='magenta')}"
                )
            else:
                click.echo(
                    "\n  "
                    + click.style(
                        f"CAPABILITIES (CTRL_EVENT @ 124: {ctrl_event:#018b})",
                        bold=True,
                        fg="magenta",
                    )
                )
                for name, _ in device.ctrl_event_bits:
                    if name in caps:
                        click.echo(f"    {name:<20s}  {'yes' if caps[name] else 'no'}")

    click.echo(f"\n{sep}")


# ═══════════════════════════════════════════════════════════════════════
#  Write command
# ═══════════════════════════════════════════════════════════════════════


@cli.command()
@click.argument("address")
@click.argument("field")
@click.argument("value")
def write(address, field, value):
    """Write a register on a Bluetti device.

    \b
    Examples:
      bluetti-cli write AA:BB:CC:DD:EE:FF ac_output on
      bluetti-cli write AA:BB:CC:DD:EE:FF dc_output off
      bluetti-cli write AA:BB:CC:DD:EE:FF charging_mode turbo
    """
    address = address.upper()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        device_name = loop.run_until_complete(lookup_device_name(address))
    finally:
        loop.close()

    device = build_device(address, device_name)

    if not device.has_field_setter(field):
        click.secho(f"Unknown writable field: {field}", fg="red")
        click.echo(f"Available fields: {', '.join(device.WRITABLE_FIELD_NAMES)}")
        sys.exit(1)

    try:
        cmd = device.build_setter_command(field, value)
    except (ValueError, KeyError) as e:
        click.secho(f"Invalid value for {field}: {value} ({e})", fg="red")
        sys.exit(1)

    client = BluetoothClient(address)
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


# ═══════════════════════════════════════════════════════════════════════
#  MQTT bridge command
# ═══════════════════════════════════════════════════════════════════════


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
      bluetti-cli mqtt-publish AA:BB:CC:DD:EE:FF --broker 192.168.1.100
    """
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    from .bus import EventBus
    from .device_handler import DeviceHandler, SourceChangeWatcher, _watch_source_changes
    from .mqtt_client import MQTTClient

    address = address.upper()

    if serial:
        device = build_device(address, address)
        device.sn = serial
    else:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            device_name = loop.run_until_complete(lookup_device_name(address))
        finally:
            loop.close()
        device = build_device(address, device_name)
    bus = EventBus()
    handler = DeviceHandler(address, device, interval, bus)
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


# ═══════════════════════════════════════════════════════════════════════
#  Load test command
# ═══════════════════════════════════════════════════════════════════════


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
      bluetti-cli load-test AA:BB:CC:DD:EE:FF -l 500 -p "500W heater on AC"
    """
    from datetime import datetime

    if interval < load_test.MIN_INTERVAL:
        raise click.BadParameter(f"Interval must be at least {load_test.MIN_INTERVAL} seconds.")

    address = address.upper()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        device_name = loop.run_until_complete(lookup_device_name(address))
    finally:
        loop.close()

    device = build_device(address, device_name)

    if output is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"ac2a_load_test_{ts}.csv"

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(load_test.run_load_test(device, output, interval, expected_load, phase))
    except KeyboardInterrupt:
        click.echo("\nInterrupted.")
    except Exception as exc:
        click.secho(f"\nError: {exc}", fg="red")
    finally:
        _close_loop(loop)


# ═══════════════════════════════════════════════════════════════════════
#  Generate systemd service
# ═══════════════════════════════════════════════════════════════════════


@cli.command("mqtt-publish-service")
@click.argument("address")
@click.option("--serial", help="Device serial number (pre-set for MQTT topic).")
@click.option("--broker", required=True, help="MQTT broker hostname.")
@click.option("--port", type=int, default=1883, show_default=True, help="MQTT broker port.")
@click.option("--username", help="MQTT broker username.")
@click.option("--password", help="MQTT broker password (visible in service file).")
@click.option("--interval", type=int, default=0, show_default=True, help="Poll interval in seconds.")
@click.option(
    "--ha-config",
    type=click.Choice(["normal", "none", "advanced"]),
    default="normal",
    show_default=True,
    help="Home Assistant discovery mode.",
)
@click.option("--user", help="System user to run service as (default: current user).")
@click.option("--exec", "exec_path", help="Path to bluetti-cli executable (default: auto-detect).")
@click.option("-o", "--output", type=click.Path(writable=True), help="Write to file instead of stdout.")
def mqtt_publish_service(
    address, serial, broker, port, username, password, interval, ha_config, user, exec_path, output
):
    """Generate a systemd unit file for mqtt-publish.

    Prints a service file to stdout (or --output). The file includes
    install instructions in comment lines at the top.
    """
    address = address.upper()

    # Resolve device SN if not provided
    if serial:
        device = build_device(address, address)
        device.sn = serial
    else:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            device_name = loop.run_until_complete(lookup_device_name(address, timeout=1.0))
        except Exception:
            device_name = address
        finally:
            loop.close()
        device = build_device(address, device_name)

    # Executable path
    if exec_path:
        exe = exec_path
    else:
        exe = shutil.which("bluetti-cli") or sys.argv[0]

    # Run-as user
    if user:
        run_user = user
    else:
        try:
            run_user = pwd.getpwuid(os.getuid()).pw_name
        except Exception:
            run_user = "root"

    # Build ExecStart args
    args = f"mqtt-publish {address} --serial {device.sn} --broker {broker}"
    if port != 1883:
        args += f" --port {port}"
    if username:
        args += f" --username {username}"
    if password:
        args += f" --password '{password}'"
    if interval:
        args += f" --interval {interval}"
    if ha_config != "normal":
        args += f" --ha-config {ha_config}"
    args += " --restart-on-source-change"

    service_name = f"bluetti-mqtt-{device.sn}"

    lines = [
        f"# Bluetti {device.type} MQTT bridge — systemd service",
        f"# Generated by: bluetti-cli generate-service {address} --broker {broker}",
        "#",
        "# To install:",
        f"#   sudo cp {service_name}.service /etc/systemd/system/",
        "#   sudo systemctl daemon-reload",
        f"#   sudo systemctl enable --now {service_name}",
        "#",
        f"# To view logs:   journalctl -u {service_name} -f",
        f"# To edit:        sudo systemctl edit --full {service_name}",
        f"# To stop:        sudo systemctl stop {service_name}",
        "#",
    ]

    if password:
        lines += [
            "# ⚠  Password is stored in this file. Remove --password from",
            "#    ExecStart and use a credentials file for production deployments.",
            "#",
        ]

    lines += [
        "# ⚠  BLE scanning requires CAP_NET_ADMIN. If the service fails to",
        "#    connect, uncomment the AmbientCapabilities line below.",
        "#",
        "",
        "[Unit]",
        f"Description=Bluetti {device.type} MQTT bridge ({device.sn})",
        "After=network-online.target bluetooth.target",
        "Wants=network-online.target bluetooth.target",
        "",
        "[Service]",
        "Type=simple",
        f"User={run_user}",
        f"ExecStart={exe} {args}",
        "Restart=always",
        "RestartSec=30",
        "Environment=PYTHONUNBUFFERED=1",
        "# AmbientCapabilities=CAP_NET_ADMIN",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
        "",
    ]

    content = "\n".join(lines)

    if output:
        with open(output, "w") as f:
            f.write(content)
        click.echo(f"Service file written to {output}")
    else:
        click.echo(content, nl=False)


# ═══════════════════════════════════════════════════════════════════════
#  MQTT listener — shutdown watchdog
# ═══════════════════════════════════════════════════════════════════════


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
      bluetti-cli mqtt-listen --serial 2409000123456 --broker 192.168.1.100
      bluetti-cli mqtt-listen AA:BB:CC:DD:EE:FF --broker 192.168.1.100
    """
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    from .device_handler import SourceChangeWatcher, _watch_source_changes
    from .shutdown_watch import run_shutdown_listener

    if not address and not serial:
        raise click.UsageError("Provide ADDRESS, --serial, or both.")

    if address:
        address = address.upper()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            device_name = loop.run_until_complete(lookup_device_name(address))
        finally:
            loop.close()
        _device = build_device(address, device_name)
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


# ═══════════════════════════════════════════════════════════════════════
#  Generate mqtt-listen service
# ═══════════════════════════════════════════════════════════════════════


@cli.command("mqtt-listen-service")
@click.option("--serial", required=True, help="Device serial number.")
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
@click.option("--user", help="System user to run service as (default: root).")
@click.option("--exec", "exec_path", help="Path to bluetti-cli executable (default: auto-detect).")
@click.option("-o", "--output", type=click.Path(writable=True), help="Write to file instead of stdout.")
def mqtt_listen_service(serial, broker, port, username, password, shutdown_at, grace_period, user, exec_path, output):
    """Generate a systemd unit file for mqtt-listen.

    Prints a service file to stdout (or --output). The file includes
    install instructions in comment lines at the top.
    """
    # Run-as user
    run_user = user or "root"

    # Executable path
    if exec_path:
        exe = exec_path
    else:
        exe = shutil.which("bluetti-cli") or sys.argv[0]

    # Build ExecStart args
    args = f"mqtt-listen --serial {serial} --broker {broker}"
    if port != 1883:
        args += f" --port {port}"
    if username:
        args += f" --username {username}"
    if password:
        args += f" --password '{password}'"
    if shutdown_at != 10:
        args += f" --shutdown-at {shutdown_at}"
    if grace_period != 60:
        args += f" --grace-period {grace_period}"
    args += " --restart-on-source-change"

    service_name = f"bluetti-shutdown-{serial}"

    lines = [
        "# Bluetti shutdown watchdog — systemd service",
        f"# Generated by: bluetti-cli mqtt-listen-service --serial {serial} --broker {broker}",
        "#",
        "# To install:",
        f"#   sudo cp {service_name}.service /etc/systemd/system/",
        "#   sudo systemctl daemon-reload",
        f"#   sudo systemctl enable --now {service_name}",
        "#",
        f"# To view logs:   journalctl -u {service_name} -f",
        f"# To edit:        sudo systemctl edit --full {service_name}",
        f"# To stop:        sudo systemctl stop {service_name}",
        "#",
        "# ⚠  This service runs as root to execute shutdown.",
        "#    The shutdown is latched — once SOC drops below the threshold,",
        "#    the countdown cannot be cancelled by SOC recovery.",
        "#    Use 'systemctl stop' to abort before the grace period expires.",
        "#",
    ]

    if password:
        lines += [
            "# ⚠  Password is stored in this file. Remove --password from",
            "#    ExecStart and use a credentials file for production deployments.",
            "#",
        ]

    lines += [
        "",
        "[Unit]",
        f"Description=Bluetti shutdown watchdog ({serial})",
        "After=network-online.target",
        "Wants=network-online.target",
        "",
        "[Service]",
        "Type=simple",
        f"User={run_user}",
        f"ExecStart={exe} {args}",
        "Restart=always",
        "RestartSec=30",
        "Environment=PYTHONUNBUFFERED=1",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
        "",
    ]

    content = "\n".join(lines)

    if output:
        with open(output, "w") as f:
            f.write(content)
        click.echo(f"Service file written to {output}")
    else:
        click.echo(content, nl=False)


if __name__ == "__main__":
    cli()

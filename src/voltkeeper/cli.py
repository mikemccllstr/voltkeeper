# ABOUTME: Voltkeeper CLI for Bluetti power stations — scan, status, verbose status. Uses layered architecture.

import asyncio
import getpass
import json
import shutil
import sys

import click

from . import load_test
from .annotate import annotate_loop
from .bluetooth import (
    ScanResult,
    build_device,
    device_registry,
    is_supported_device_type,
    lookup_scan_result,
    pick_address_after_scan,
)
from .bluetooth.client import BluetoothClient
from .bluetooth.exc import BadConnectionError, ModbusError, ParseError
from .config import load_config, write_config
from .core.commands import ReadHoldingRegisters
from .probe import emit_yaml, probe_device
from .validate import validate_profile

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
        click.echo(f"  {click.style(f'voltkeeper status {devices[0].address}', bold=True)}")
    else:
        click.echo("To read data from a specific device:")
        for sr in devices:
            cmd = click.style(f"voltkeeper status {sr.address}", bold=True)
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
@click.option(
    "--daemon",
    type=str,
    default=None,
    help="Query the voltkeeperd daemon at this URL instead of connecting directly via BLE "
    "(e.g. http://localhost:8080 or just 'localhost').",
)
def status(address, timeout, verbose, daemon):
    """Read battery SOC and pack data from a Bluetti device.

    If ADDRESS is not provided, scans for nearby Bluetti devices and
    lets you pick one interactively.
    """
    if daemon:
        _status_via_daemon(daemon, address, verbose)
        return

    if not address:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            sr = loop.run_until_complete(pick_address_after_scan())
        finally:
            loop.close()
        address = sr.address
        device_name = sr.name
        encrypted = sr.encrypted or False
        tip = click.style(f"voltkeeper status {address}", bold=True)
        click.echo(f"\nTip: next time, run directly with:\n  {tip}")
    else:
        address = address.upper()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            sr = loop.run_until_complete(lookup_scan_result(address))
        finally:
            loop.close()
        device_name = sr.name
        encrypted = sr.encrypted or False

    device = build_device(address, device_name)
    client = BluetoothClient(address, encrypted=encrypted)

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


def _field_hint(field_obj) -> str:
    from .core.struct import BoolField, EnumField, UintField

    if isinstance(field_obj, BoolField):
        return "[on|off]"
    if isinstance(field_obj, EnumField):
        opts = "|".join(m.name.lower() for m in field_obj.enum)
        return f"[{opts}]"
    if isinstance(field_obj, UintField):
        unit = field_obj.unit or ""
        if field_obj.range is not None:
            lo, hi = field_obj.range
            return f"[{lo}-{hi}]{unit}"
        return f"[integer]{unit}"
    return ""


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
        status_map = {3: "Normal", 4: "Normal", 5: "Normal", 7: "Abnormal"}
        status_val = home["invWorkingStatus"]
        label = status_map.get(status_val, "Unknown")
        misc_parts.append(f"Inv Status={status_val} ({label})")
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

            field_obj = next((f for f in device.control_struct.fields if f.name == name), None)
            unit = getattr(field_obj, "unit", None) or ""
            if unit:
                display = f"{display}{unit}"
            elif name == "system_timezone" and isinstance(val, int) and val != 0:
                display = f"UTC{'+' if val > 0 else ''}{val}"

            hint = _field_hint(field_obj) if field_obj else ""
            hint_str = click.style(hint, dim=True) if hint else ""
            click.echo(f"    {name:<20s}  {display:<12s}  {hint_str}")

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


def _show_field_help(field_name: str, address: str) -> None:
    """Display type, enum values, and range for a writable field."""
    import asyncio as _asyncio

    loop = _asyncio.new_event_loop()
    _asyncio.set_event_loop(loop)
    try:
        sr = loop.run_until_complete(lookup_scan_result(address))
    finally:
        loop.close()

    device = build_device(address, sr.name)

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

    device = build_device(address, sr.name)

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
      voltkeeper mqtt-publish AA:BB:CC:DD:EE:FF --broker 192.168.1.100
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
            sr = loop.run_until_complete(lookup_scan_result(address, timeout=1.0))
        except Exception:
            sr = ScanResult(address=address, name=address, encrypted=None)
        finally:
            loop.close()
        device = build_device(address, sr.name)
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
      voltkeeper load-test AA:BB:CC:DD:EE:FF -l 500 -p "500W heater on AC"
    """
    from datetime import datetime

    if interval < load_test.MIN_INTERVAL:
        raise click.BadParameter(f"Interval must be at least {load_test.MIN_INTERVAL} seconds.")

    address = address.upper()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        sr = loop.run_until_complete(lookup_scan_result(address))
    finally:
        loop.close()

    device = build_device(address, sr.name)

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
@click.option("--exec", "exec_path", help="Path to voltkeeper executable (default: auto-detect).")
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
            sr = loop.run_until_complete(lookup_scan_result(address, timeout=1.0))
        except Exception:
            sr = ScanResult(address=address, name=address, encrypted=None)
        finally:
            loop.close()
        device = build_device(address, sr.name)

    # Executable path
    if exec_path:
        exe = exec_path
    else:
        exe = shutil.which("voltkeeper") or sys.argv[0]

    # Run-as user
    if user:
        run_user = user
    else:
        try:
            run_user = getpass.getuser()
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

    service_name = f"voltkeeper-mqtt-{device.sn}"

    lines = [
        f"# Bluetti {device.type} MQTT bridge — systemd service",
        f"# Generated by: voltkeeper generate-service {address} --broker {broker}",
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
      voltkeeper mqtt-listen --serial 2409000123456 --broker 192.168.1.100
      voltkeeper mqtt-listen AA:BB:CC:DD:EE:FF --broker 192.168.1.100
    """
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    from .device_handler import SourceChangeWatcher, _watch_source_changes
    from .shutdown_watch import _is_shutdown_supported, run_shutdown_listener

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
        _device = build_device(address, sr.name)
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
@click.option("--exec", "exec_path", help="Path to voltkeeper executable (default: auto-detect).")
@click.option("-o", "--output", type=click.Path(writable=True), help="Write to file instead of stdout.")
def mqtt_listen_service(serial, broker, port, username, password, shutdown_at, grace_period, user, exec_path, output):
    """Generate a systemd unit file for mqtt-listen.

    Prints a service file to stdout (or --output). The file includes
    install instructions in comment lines at the top.
    """
    from .shutdown_watch import _is_shutdown_supported

    if not _is_shutdown_supported():
        raise click.ClickException("System shutdown via mqtt-listen-service is only supported on Linux")

    # Run-as user
    run_user = user or "root"

    # Executable path
    if exec_path:
        exe = exec_path
    else:
        exe = shutil.which("voltkeeper") or sys.argv[0]

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

    service_name = f"voltkeeper-shutdown-{serial}"

    lines = [
        "# Bluetti shutdown watchdog — systemd service",
        f"# Generated by: voltkeeper mqtt-listen-service --serial {serial} --broker {broker}",
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


@cli.command()
@click.argument("address")
@click.option("-o", "--output", default=None, help="Output YAML file (default: hardware-data/verify-MODEL-DATE.yaml)")
@click.option("--tier", "max_tier", default=6, type=int, help="Run through this tier only (1–6).")
@click.option("--yes", "pre_consent", is_flag=True, default=False, help="Pre-consent to all supervised tiers.")
@click.option("--no-scrub", "no_scrub", is_flag=True, default=False, help="Keep real SN and BLE address in report.")
def verify(address: str, output: str | None, max_tier: int, pre_consent: bool, no_scrub: bool) -> None:
    """Run a six-tier integration test against a Bluetti device.

    \b
    Tiers 1-3 run automatically (read, identity writes, probe writes).
    Tiers 4-6 prompt before running (load toggles, mode changes, irreversible).

    \b
    The output YAML report is safe to share in a GitHub issue:
      https://github.com/mikemccllstr/voltkeeper/issues
    """
    import datetime

    from .core.verify import (
        TierResult,
        build_tier_plan,
        run_tier1,
        run_tier2,
        run_tier3,
        run_tier_supervised,
    )

    TIER_DESCRIPTIONS = {
        4: "load-affecting toggles (ac_output, dc_output, ctrl_grid, ctrl_feed, power_lifting, eco_mode)",
        5: "operating mode changes (working_mode, ups_mode)",
        6: "IRREVERSIBLE operations (factory_reset, system_power, power_off)",
    }
    TIER_CONSENT_LABEL = {
        4: "pre-granted (--yes)",
        5: "pre-granted (--yes)",
        6: "pre-granted (--yes)",
    }

    address = address.upper()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        sr = loop.run_until_complete(lookup_scan_result(address))
    finally:
        loop.close()

    device = build_device(address, sr.name)
    tier_plan = build_tier_plan(device)

    if output is None:
        today = datetime.date.today().isoformat()
        output = f"hardware-data/verify-{device.type}-{today}.yaml"

    client = BluetoothClient(address, encrypted=sr.encrypted or False)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    tier_results: list[TierResult] = []
    tier1_values: dict = {}

    try:
        loop.run_until_complete(client.connect())
        click.echo(f"Connected to {device.type} ({address})")

        # ── Tier 1: read & parse ───────────────────────────────────────
        click.echo("Tier 1  reading all blocks ...", nl=False)
        t1, tier1_values = loop.run_until_complete(run_tier1(client, device))
        tier_results.append(t1)
        _print_tier_summary(t1)
        if t1.failure_count and max_tier > 1:
            click.secho(
                f"  ⚠ {t1.failure_count} issue(s) found — consider sharing the report before continuing",
                fg="yellow",
            )
        if max_tier < 2:
            _skip_remaining(tier_results, tier_plan, 2, "tier limit")
            _finish(device, address, tier_results, tier1_values, output, no_scrub)
            return

        # ── Tier 2: identity writes ────────────────────────────────────
        fields2 = tier_plan.get(2, [])
        if fields2:
            click.echo(f"Tier 2  identity writes ({len(fields2)} fields) ...", nl=False)
            t2 = loop.run_until_complete(run_tier2(client, device, tier1_values, fields2))
        else:
            t2 = TierResult(tier=2, status="pass", reason="no automatic fields")
        tier_results.append(t2)
        _print_tier_summary(t2)
        if t2.failure_count and max_tier > 2:
            click.secho(
                f"  ⚠ {t2.failure_count} issue(s) found — consider sharing the report before continuing",
                fg="yellow",
            )
        if max_tier < 3:
            _skip_remaining(tier_results, tier_plan, 3, "tier limit")
            _finish(device, address, tier_results, tier1_values, output, no_scrub)
            return

        # ── Tier 3: probe writes ───────────────────────────────────────
        fields3 = tier_plan.get(3, [])
        if fields3:
            click.echo(f"Tier 3  probe writes ({len(fields3)} fields) ...", nl=False)
            t3 = loop.run_until_complete(run_tier3(client, device, tier1_values, fields3))
        else:
            t3 = TierResult(tier=3, status="pass", reason="no automatic fields")
        tier_results.append(t3)
        _print_tier_summary(t3)
        if t3.failure_count and max_tier > 3:
            click.secho(
                f"  ⚠ {t3.failure_count} issue(s) found — consider sharing the report before continuing",
                fg="yellow",
            )

        # ── Tiers 4, 5, 6: supervised ─────────────────────────────────
        consent: str | None = None
        for tier_num in (4, 5, 6):
            if max_tier < tier_num:
                _skip_remaining(tier_results, tier_plan, tier_num, "tier limit")
                continue

            fields = tier_plan.get(tier_num, [])
            if not fields:
                tier_results.append(
                    TierResult(tier=tier_num, status="skipped", reason="no fields at this tier for this device")
                )
                continue

            desc = TIER_DESCRIPTIONS[tier_num]
            if tier_num == 6:
                click.echo(f"\nTier 6  ⚠ IRREVERSIBLE: {desc}")
                if pre_consent:
                    consent = TIER_CONSENT_LABEL[6]
                    proceed = True
                else:
                    typed = click.prompt(
                        '  Type "I understand this is irreversible" to proceed, or Enter to skip',
                        default="",
                    )
                    proceed = typed.strip() == "I understand this is irreversible"
                    consent = "typed confirmation" if proceed else None
            else:
                click.echo(f"\nTier {tier_num}  {desc}")
                if pre_consent:
                    proceed = True
                    consent = TIER_CONSENT_LABEL[tier_num]
                else:
                    proceed = click.confirm("  Continue?", default=False)
                    consent = "user confirmed" if proceed else None

            if not proceed:
                tier_results.append(TierResult(tier=tier_num, status="skipped", reason="user declined"))
                continue

            click.echo(f"  Running tier {tier_num} ({len(fields)} fields) ...", nl=False)
            t = loop.run_until_complete(
                run_tier_supervised(client, device, tier1_values, fields, tier_num, consent=consent)
            )
            tier_results.append(t)
            _print_tier_summary(t)
            if t.failure_count and tier_num < 6:
                click.secho(
                    f"  ⚠ {t.failure_count} issue(s) found — consider sharing the report before continuing",
                    fg="yellow",
                )

    except KeyboardInterrupt:
        click.echo("\nInterrupted.")
    except Exception as exc:
        click.secho(f"Error: {exc}", fg="red")
    finally:
        loop.run_until_complete(client.disconnect())
        _close_loop(loop)

    _finish(device, address, tier_results, tier1_values, output, no_scrub)


def _print_tier_summary(t) -> None:
    total = len(t.blocks) + len(t.fields)
    fails = t.failure_count
    icon = "✓" if t.status in ("pass", "skipped") else "✗"
    status_str = t.status if t.status == "skipped" else f"{total - fails}/{total} ok"
    click.echo(f"  {icon} {status_str}")


def _skip_remaining(
    results: list,
    tier_plan: dict,
    from_tier: int,
    reason: str,
) -> None:
    from .core.verify import TierResult

    for n in range(from_tier, 7):
        if any(t.tier == n for t in results):
            continue
        results.append(TierResult(tier=n, status="skipped", reason=reason))


def _finish(
    device,
    address: str,
    tier_results: list,
    tier1_values: dict,
    output: str,
    no_scrub: bool,
) -> None:
    from . import _version
    from .core.verify import build_report, write_report

    report = build_report(
        device,
        sn=device.sn,
        address=address,
        tier_results=tier_results,
        tier1_values=tier1_values,
        scrub=not no_scrub,
        voltkeeper_version=_version.__version__,
    )
    write_report(report, output)
    click.echo(f"\nReport written to: {output}")
    click.secho(
        "Share this file in a GitHub issue: https://github.com/mikemccllstr/voltkeeper/issues",
        fg="cyan",
    )


@cli.command()
@click.argument("address")
@click.option("-o", "--output", default="profile.yaml", help="Output YAML file path")
def probe(address: str, output: str) -> None:
    """Probe a Bluetti device and emit a draft profile YAML.

    The serial number in the saved YAML is replaced with a synthetic
    placeholder so the file is safe to commit or share.  The real SN
    is shown to you on stdout.
    """
    from .scrub import SYNTHETIC_SN_STR, scrub_profile, split_model_sn

    address = address.upper()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        sr = loop.run_until_complete(lookup_scan_result(address))
    finally:
        loop.close()

    profile = asyncio.run(probe_device(address, sr.name, encrypted=bool(sr.encrypted)))

    parts = split_model_sn(sr.name or "")
    if parts:
        model, real_sn = parts
        click.echo(f"Probed {model} SN {real_sn} ({len(profile.get('blocks', {}))} blocks)")
    else:
        click.echo(f"Probed {sr.name or address} ({len(profile.get('blocks', {}))} blocks)")

    emit_yaml(scrub_profile(profile), output)
    click.echo(f"Wrote profile draft to {output} (SN scrubbed to {SYNTHETIC_SN_STR} for privacy)")


@cli.command("annotate")
@click.argument("address")
@click.option("-o", "--output", default="draft.yaml", help="Output YAML draft file")
def annotate(address: str, output: str) -> None:
    """Live-poll a device and annotate changing register values.

    Connect, sweep register blocks, and highlight byte-level
    changes in real time.  At each changed register offset you
    are prompted for a field name; type a name to record the
    annotation, or press Enter to skip.

    Saves to *output* incrementally (Ctrl-C safe).
    """
    from pathlib import Path

    address = address.upper()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        sr = loop.run_until_complete(lookup_scan_result(address))
    finally:
        loop.close()

    asyncio.run(annotate_loop(address, Path(output), encrypted=bool(sr.encrypted), device_name=sr.name))


@cli.command("validate-profile")
@click.argument("yaml_path")
def validate_profile_cmd(yaml_path: str) -> None:
    """Validate a probe YAML against field sanity checks.

    Loads a profile YAML (from ``voltkeeper probe``), parses
    each register block with the device model's parser, and flags
    fields with stuck-at values (0, 0xFFFF, 0xFFFFFFFF) or
    out-of-range values.
    """
    verdicts = validate_profile(yaml_path)
    if not verdicts:
        click.echo("No fields to validate (unknown model or empty profile).")
        return

    ok = sum(1 for v in verdicts if v.status == "ok")
    suspect = sum(1 for v in verdicts if v.status == "suspect")
    error = sum(1 for v in verdicts if v.status == "error")

    click.echo(f"Fields: {ok} ok, {suspect} suspect, {error} error\n")

    for v in verdicts:
        line = f"  [{v.status.upper()}] {v.name}: {v.value}"
        if v.note:
            line += f"  ({v.note})"
        if v.status == "ok":
            click.secho(line, fg="green")
        elif v.status == "suspect":
            click.secho(line, fg="yellow")
        else:
            click.secho(line, fg="red", bold=True)


# ═══════════════════════════════════════════════════════════════════════
#  Daemon management
# ═══════════════════════════════════════════════════════════════════════


@cli.group()
def daemon():
    """Manage the voltkeeperd daemon process."""


@daemon.command("start")
def daemon_start():
    """Start the voltkeeperd daemon.

    Run voltkeeperd in the foreground. For production use, set up
    a systemd service unit.
    """
    from .daemon import main as daemon_main

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

    from .config import Config, ServerConfig, find_writable_config_path

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
    except SystemExit:
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


# ═══════════════════════════════════════════════════════════════════════
#  Daemon-mode helpers
# ═══════════════════════════════════════════════════════════════════════


def _resolve_daemon_url(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw.rstrip("/")
    return f"http://{raw.rstrip('/')}:8080"


def _discover_api_key() -> str | None:
    try:
        config = load_config()
        return config.server.api_key
    except SystemExit:
        return None


def _status_via_daemon(raw_url: str, address: str | None, verbose: bool) -> None:
    url = _resolve_daemon_url(raw_url)
    api_key = _discover_api_key()

    import json as _json
    from urllib.error import URLError
    from urllib.request import Request, urlopen

    if address:
        req = Request(f"{url}/api/device/{address.upper()}")
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")
        try:
            with urlopen(req, timeout=10) as resp:
                if resp.status == 404:
                    click.secho(f"Device {address.upper()} not found on daemon.", fg="red")
                    return
                if resp.status == 401:
                    click.secho("Unauthorized. Check API key in voltkeeperd config.", fg="red")
                    return
                data = _json.loads(resp.read().decode())
        except URLError as e:
            click.secho(f"Error connecting to daemon at {url}: {e}", fg="red")
            return
    else:
        req = Request(f"{url}/api/devices")
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")
        try:
            with urlopen(req, timeout=10) as resp:
                devices = _json.loads(resp.read().decode())
        except URLError as e:
            click.secho(f"Error connecting to daemon at {url}: {e}", fg="red")
            return

        if not devices:
            click.echo("No devices configured on daemon.")
            return

        if len(devices) == 1:
            address = devices[0]["address"]
        else:
            click.echo(f"{len(devices)} devices found on daemon:\n")
            for i, d in enumerate(devices, 1):
                click.echo(f"  [{i}] {d['address']}  {d.get('name', '')}  ({d.get('type', '?')})  [{d['status']}]")
            click.echo()
            try:
                choice = input("Select device number: ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(devices):
                    address = devices[idx]["address"]
                else:
                    click.secho("Invalid selection.", fg="red")
                    return
            except (ValueError, EOFError, KeyboardInterrupt):
                return

        req = Request(f"{url}/api/device/{address}")
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")
        try:
            with urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read().decode())
        except URLError as e:
            click.secho(f"Error connecting to daemon: {e}", fg="red")
            return

    status = data.pop("_status", "unknown")
    device_type = data.pop("type", "?")
    name = data.pop("name", address)
    del data["address"]

    click.echo()
    click.secho(f"{name} ({device_type})", bold=True)
    click.echo("  Status: ", nl=False)
    status_color = {"online": "green", "missing": "yellow", "new": "blue"}.get(status, "white")
    click.secho(status.upper(), fg=status_color)

    if not data:
        click.echo("  (no state data available)")
        return

    soc = data.pop("packTotalSoc", None)
    if soc is not None:
        click.echo(f"  Battery: {round(soc)}%")

    for key, value in data.items():
        if isinstance(value, float):
            click.echo(f"  {key}: {value:.1f}")
        elif value is not None:
            click.echo(f"  {key}: {value}")


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


# ═══════════════════════════════════════════════════════════════════════
#  Config management commands
# ═══════════════════════════════════════════════════════════════════════

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
    from .config import CONFIG_SEARCH_PATHS, _find_config

    try:
        config_path = _find_config()
    except SystemExit:
        click.secho("No config file found. Searched:", fg="red")
        for p in CONFIG_SEARCH_PATHS:
            click.echo(f"  {p}")
        sys.exit(1)

    cfg = load_config(config_path)
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
    from .config import find_writable_config_path, write_config

    if key not in _CONFIG_SETTABLE:
        click.secho(f"Unknown key: {key}", fg="red")
        click.echo("Valid keys: " + ", ".join(sorted(_CONFIG_SETTABLE)))
        sys.exit(1)

    config_path = find_writable_config_path()
    if config_path.exists():
        cfg = load_config(config_path)
    else:
        click.secho(f"No config file found; creating {config_path}", fg="yellow")
        from .config import Config, ServerConfig

        cfg = Config(server=ServerConfig(api_key=""))

    # Apply the value
    from .config import ScanConfig
    from .config import ServerConfig as _SC

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
    from .config import DeviceEntry, find_writable_config_path, write_config

    address = address.upper()
    config_path = find_writable_config_path()
    if config_path.exists():
        cfg = load_config(config_path)
    else:
        from .config import Config, ServerConfig

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
    from .config import find_writable_config_path, write_config

    address = address.upper()
    config_path = find_writable_config_path()
    if not config_path.exists():
        click.echo(f"Device {address} not found in config (no config file).")
        return

    cfg = load_config(config_path)
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


if __name__ == "__main__":
    cli()

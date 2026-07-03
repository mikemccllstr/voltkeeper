# ABOUTME: CLI status commands — read battery data, power sections, and verbose output formatting.

import asyncio
import sys

import click

from voltkeeper.bluetooth import lookup_scan_result, pick_address_after_scan
from voltkeeper.bluetooth.client import BluetoothClient
from voltkeeper.bluetooth.exc import BadConnectionError, ModbusError, ParseError
from voltkeeper.cli import cli
from voltkeeper.cli._helpers import _close_loop, _device_from_scan, _discover_api_key, _resolve_daemon_url
from voltkeeper.core.commands import ReadHoldingRegisters, TlvReadHoldingRegisters
from voltkeeper.core.struct import BoolField, EnumField, UintField
from voltkeeper.core.utils import format_version


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
        encrypted = sr.encrypted or False

    device = _device_from_scan(sr)
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
                    if isinstance(cmd_obj, TlvReadHoldingRegisters):
                        from voltkeeper.core.tlv import TlvParser

                        for item in TlvParser.parse(raw):
                            controls.update(device.parse(item.reg_addr, item.value))
                    else:
                        controls.update(device.parse(cmd_obj.starting_address, raw))
                except ModbusError:
                    # Control registers (2000+) are write-only on some models;
                    # read attempts return Modbus exceptions — expected.
                    pass
                except (ParseError, BadConnectionError) as exc:
                    start = cmd_obj.starting_address if hasattr(cmd_obj, "starting_address") else "(tlv)"
                    click.secho(f"  ⚠  control read at {start} failed: {exc}", fg="yellow")
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


def _print_power_section(home: dict, indent: str, show_zeros: bool) -> None:
    pv_w = home.get("totalPVPower", 0)
    ac_w = home.get("totalACPower", 0)
    dc_w = home.get("totalDCPower", 0)
    grid_w = home.get("totalGridPower", 0)

    has_pv = "totalPVPower" in home
    has_ac = "totalACPower" in home
    has_dc = "totalDCPower" in home
    has_grid = "totalGridPower" in home

    # battery = ac + dc − pv − grid (positive = discharging, negative = charging)
    battery_w = ac_w + dc_w - pv_w - grid_w
    can_derive_battery = has_ac or has_dc or has_pv or has_grid

    in_rows: list[tuple[str, float, str]] = []
    out_rows: list[tuple[str, float, str]] = []

    if has_pv and (show_zeros or pv_w != 0):
        in_rows.append(("PV:", pv_w, ""))
    if has_grid and grid_w > 0:
        in_rows.append(("Grid import:", grid_w, ""))
    if can_derive_battery and battery_w > 0:
        in_rows.append(("Battery:", battery_w, "  (discharging)"))
    elif can_derive_battery and show_zeros and battery_w == 0:
        in_rows.append(("Battery:", 0, ""))

    if has_ac and ac_w > 0:
        out_rows.append(("AC loads:", ac_w, ""))
    if has_dc and (show_zeros or dc_w != 0):
        out_rows.append(("DC loads:", dc_w, ""))
    if has_grid and grid_w < 0:
        out_rows.append(("Grid export:", abs(grid_w), ""))
    if has_ac and ac_w < 0:
        out_rows.append(("AC export:", abs(ac_w), ""))
    if can_derive_battery and battery_w < 0:
        out_rows.append(("Battery:", abs(battery_w), "  (charging)"))

    in_total = sum(v for _, v, _ in in_rows)
    out_total = sum(v for _, v, _ in out_rows)
    cont = indent + "     "

    def _row(side_tag: str, label: str, value: float, hint: str) -> None:
        click.echo(f"{indent}{side_tag}{label:<14}{value:>5.0f} W{hint}")

    for i, (label, value, hint) in enumerate(in_rows):
        _row("IN   " if i == 0 else "     ", label, value, hint)
    if not in_rows:
        click.echo(f"{indent}IN")
    click.echo(f"{cont}Total:        {in_total:>5.0f} W")

    for i, (label, value, hint) in enumerate(out_rows):
        _row("OUT  " if i == 0 else "     ", label, value, hint)
    if not out_rows:
        click.echo(f"{indent}OUT")
    click.echo(f"{cont}Total:        {out_total:>5.0f} W")


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
    if any(k in home for k in ("totalPVPower", "totalACPower", "totalDCPower", "totalGridPower")):
        _print_power_section(home, indent="  ", show_zeros=False)
    click.echo(sep)


def _field_hint(field_obj) -> str:

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
    if any(k in home for k in ("totalPVPower", "totalACPower", "totalDCPower", "totalGridPower")):
        click.echo(f"\n  {click.style('POWER (instantaneous)', bold=True, fg='cyan')}")
        _print_power_section(home, indent="    ", show_zeros=True)

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
    ver_keys = [k for k in inv_base if k.endswith("_version")]
    if ver_keys:
        click.echo(f"\n  {click.style('SOFTWARE VERSIONS', bold=True, fg='magenta')}")
        for k in sorted(ver_keys):
            label = k.removesuffix("_version").replace("_", " ").upper()
            click.echo(f"    {label}:  {format_version(inv_base[k])}")

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

    # ── IoT Module ──
    _iot_keys = {
        "iot_model",
        "iot_sn",
        "iot_software_ver",
        "iot_rf_ver",
        "ble_status",
        "mqtt_status",
        "wifi_ip",
        "wifi_gateway",
        "wifi_mask",
        "network_rssi",
        "wifi_mac",
        "ble_mac",
        "network_conn_mode",
    }
    if controls and any(k in controls for k in _iot_keys):
        click.echo(f"\n  {click.style('IoT MODULE', bold=True, fg='magenta')}")
        if "iot_model" in controls:
            click.echo(f"    Model:                {controls['iot_model']}")
        if "iot_sn" in controls:
            click.echo(f"    Serial:               {controls['iot_sn']}")
        if "iot_software_ver" in controls:
            click.echo(f"    Firmware:             {controls['iot_software_ver']}")
        if "iot_rf_ver" in controls:
            click.echo(f"    RF Firmware:          {controls['iot_rf_ver']}")
        conn = controls.get("network_conn_mode", "none")
        if conn and conn != "none":
            click.echo(f"    Connection:           {conn}")
            if "wifi_ip" in controls and controls["wifi_ip"] != "0.0.0.0":
                click.echo(f"    WiFi IP:              {controls['wifi_ip']}")
            if "network_rssi" in controls:
                click.echo(f"    RSSI:                 {controls['network_rssi']} dBm")
        elif "ble_status" in controls:
            click.echo(f"    Connection:           BLE {'connected' if controls['ble_status'] else 'disconnected'}")
        if "wifi_mac" in controls:
            click.echo(f"    WiFi MAC:             {controls['wifi_mac']}")

    # ── Controls (writable fields) ──
    if controls:
        click.echo(f"\n  {click.style('CONTROLS (writable)', bold=True, fg='cyan')}")
        for name, val in sorted(controls.items()):
            if name == "ctrl_event":
                continue
            if name in _iot_keys:
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


# ── Daemon-mode status helper ──


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

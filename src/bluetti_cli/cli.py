# ABOUTME: Click CLI for Bluetti power stations — scan, status, verbose status. Uses layered architecture.

import asyncio
import sys

import click

from .bluetooth import build_device, pick_address_after_scan, lookup_device_name
from .bluetooth.client import BluetoothClient
from .core.commands import ReadHoldingRegisters
from .bluetooth.exc import ModbusError

SERVICE_UUID = "0000ff00-0000-1000-8000-00805f9b34fb"


def _close_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Cancel pending tasks and cleanly close an event loop."""
    try:
        tasks = asyncio.all_tasks(loop)
        for task in tasks:
            task.cancel()
        if tasks:
            loop.run_until_complete(
                asyncio.gather(*tasks, return_exceptions=True)
            )
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
    for addr, name in devices:
        click.echo(f"  {click.style(addr, fg='green')}  \u2014  {name}")

    click.echo()
    if len(devices) == 1:
        click.echo("To read data from this device:")
        click.echo(
            f"  {click.style(f'bluetti-cli status {devices[0][0]}', bold=True)}"
        )
    else:
        click.echo("To read data from a specific device:")
        for addr, _ in devices:
            cmd = click.style(f"bluetti-cli status {addr}", bold=True)
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
            address = loop.run_until_complete(pick_address_after_scan())
        finally:
            loop.close()
        cmd = click.style(f"bluetti-cli status {address}", bold=True)
        click.echo(f"\nTip: next time, run directly with:\n  {cmd}")
        device_name = address
    else:
        address = address.upper()
        device_name = address

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
                    pass
                except Exception:
                    pass
        else:
            cmd = ReadHoldingRegisters(100, 6)
            raw = loop.run_until_complete(client.execute(cmd))
            home = device.parse(100, raw)

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
        _print_verbose(home, inv_base, pv, grid, load, inv_info, controls)
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
    click.echo(f"  Pack Current:      {home['packTotalCurrent']:>5.1f} A")
    click.echo(f"  Charging Status:   {home['packChargingStatus']:>5.0f}")
    click.echo(f"  Time to Full:      {home['packChgFullTime']:>5.0f} min")
    click.echo(f"  Time to Empty:     {home['packDsgEmptyTime']:>5.0f} min")
    click.echo(sep)


def _print_verbose(
    home: dict, inv_base: dict, pv: dict, grid: dict, load: dict, inv_info: dict,
    controls: dict = None,
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
    click.echo(f"    Time to Full:         {home.get('packChgFullTime', 0):>5.0f} min")
    click.echo(
        f"    Time to Empty:        {home.get('packDsgEmptyTime', 0):>5.0f} min"
    )
    if "packDsgEnergyTotal" in home:
        click.echo(
            f"    Total Discharged:     {home['packDsgEnergyTotal']:>8.1f} Wh"
        )

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
        click.echo(
            f"\n  {click.style('ENERGY (lifetime)', bold=True, fg='yellow')}"
        )
        if "totalPVChargingEnergy" in home:
            click.echo(
                f"    PV Charging:          {home['totalPVChargingEnergy']:>8.1f} Wh"
            )
        if "totalGridChargingEnergy" in home:
            click.echo(
                f"    Grid Charging:        {home['totalGridChargingEnergy']:>8.1f} Wh"
            )
        if "totalFeedbackEnergy" in home:
            click.echo(
                f"    Feed-back:            {home['totalFeedbackEnergy']:>8.1f} Wh"
            )
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
        click.echo(
            f"\n  {click.style('SOFTWARE VERSIONS', bold=True, fg='magenta')}"
        )
        for k in sorted(soft_keys):
            click.echo(f"    {k}: {inv_base[k]}")

    # ── PV Details ──
    pv_keys = [
        k
        for k in pv
        if k.startswith("pv[") and k.endswith(".type") and pv.get(k, 0) != 0
    ]
    if pv_keys:
        click.echo(f"\n  {click.style('PV STRINGS', bold=True, fg='cyan')}")
        for pk in sorted(set(k.split(".")[0] for k in pv_keys)):
            pv_type = pv.get(f"{pk}.type", "?")
            pv_status = pv.get(f"{pk}.workingStatus", "?")
            pv_power = pv.get(f"{pk}.inputPower", 0)
            pv_volt = pv.get(f"{pk}.inputVoltage", 0)
            pv_curr = pv.get(f"{pk}.inputCurrent", 0)
            click.echo(
                f"    {pk}: Power={pv_power}W  V={pv_volt:.1f}V  "
                f"I={pv_curr:.1f}A  Status={pv_status}  Type={pv_type}"
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
                dc_parts.append(
                    f"DC{v}={load[f'dc{v}Power']}W/{load[f'dc{v}Current']:.1f}A"
                )
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
        misc_parts.append(
            f"Charge Mode={mode_map.get(home['chargingMode'], str(home['chargingMode']))}"
        )
    if home.get("invWorkingStatus", 0):
        misc_parts.append(f"Inv Status={home['invWorkingStatus']}")
    if home.get("packAgingInfo", 0):
        misc_parts.append(f"Pack Aging={home['packAgingInfo']}")
    if home.get("gridParallelSoC", 0):
        misc_parts.append(f"Grid Parallel SoC={home['gridParallelSoC']}%")
    if home.get("rateVoltage") or home.get("rateFrequency"):
        misc_parts.append(
            f"Rated={home.get('rateVoltage', '?')}V/{home.get('rateFrequency', '?')}Hz"
        )
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

        if "ctrl_event" in controls:
            from .core.devices.ac2a import AC2A
            caps = AC2A.decode_ctrl_event(controls["ctrl_event"])
            raw_bits = controls["ctrl_event"]
            click.echo(
                f"\n  {click.style(f'CAPABILITIES (CTRL_EVENT @ 2006: {raw_bits:#018b})', bold=True, fg='magenta')}"
            )
            for name, _ in AC2A.CTRL_EVENT_BITS:
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


@cli.command()
@click.argument("address")
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
def mqtt(address, broker, port, username, password, interval, ha_config):
    """Run MQTT bridge — continuously poll device and publish to broker.

    \b
    Example:
      bluetti-cli mqtt AA:BB:CC:DD:EE:FF --broker 192.168.1.100
    """
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    from .bus import EventBus
    from .device_handler import DeviceHandler
    from .mqtt_client import MQTTClient

    address = address.upper()

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

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        async def run_bridge():
            await asyncio.gather(bus.run(), handler.run(), mqtt_client.run())

        click.echo(f"Starting MQTT bridge for {address} → {broker}:{port}")
        loop.run_until_complete(run_bridge())
    except KeyboardInterrupt:
        click.echo("\nShutting down...")
    finally:
        _close_loop(loop)
        click.echo("Stopped.")


if __name__ == "__main__":
    cli()

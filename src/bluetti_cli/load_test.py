# ABOUTME: Load test mode — coached discharge test with CSV logging and dual energy tracking.

import asyncio
import csv
from datetime import datetime, timezone
import sys
import time

import click

from .core.commands import ReadHoldingRegisters
from .bluetooth.client import BluetoothClient
from .bluetooth.exc import ModbusError

MIN_INTERVAL = 15
GRID_WARNING_W = 10
PV_WARNING_W = 10
PRE_CHECK_SOC_MIN = 95
PRE_CHECK_GRID_MAX = 5
PRE_CHECK_PV_MAX = 5
MAX_BLE_RETRIES = 3

CSV_COLUMNS = [
    "timestamp", "elapsed_s", "soc_pct", "pack_v", "pack_a",
    "dc_power_w", "ac_power_w", "total_power_w", "pv_power_w", "grid_power_w",
    "charging_status", "est_remaining_min", "ambient_temp_c", "inv_temp_c",
    "energy_computed_wh", "energy_register_wh", "phase",
]

STATUS_MAP = {0: "Idle", 1: "Charging", 2: "Discharging", 3: "Floating"}

SOC_BAR_WIDTH = 20


# ═══════════════════════════════════════════════════════════════════════
#  Public entry point (called from cli.py)
# ═══════════════════════════════════════════════════════════════════════


async def run_load_test(device, output_path, interval, expected_load, phase):
    """Run a full load-test cycle: coach → verify → poll → CSV → summary."""
    client = BluetoothClient(device.address)
    await client.connect()

    try:
        click.echo()
        if not await _verify_prerequisites(client, device):
            click.secho("\nPrerequisites not met. Aborting.", fg="red")
            return
    except Exception as exc:
        click.secho(f"\nPre-check failed: {exc}", fg="red")
        return

    click.secho("\nAll checks passed! Starting load test.\n", fg="green")
    click.echo("Press Ctrl-C to stop early.")

    csv_file = open(output_path, "w", newline="")
    writer = csv.writer(csv_file)
    _write_csv_header(writer, device, phase, expected_load, interval)

    start = time.monotonic()
    prev_power = None
    prev_elapsed = 0.0
    energy_computed = 0.0
    sample = 0
    consecutive_failures = 0

    try:
        while True:
            try:
                home = await _read_home(client, device)
            except Exception as exc:
                consecutive_failures += 1
                if consecutive_failures > MAX_BLE_RETRIES:
                    click.secho(f"\nBLE connection lost after {MAX_BLE_RETRIES} retries.", fg="red")
                    break
                click.secho(f"  Read error ({consecutive_failures}/{MAX_BLE_RETRIES}): {exc}", fg="yellow")
                await asyncio.sleep(2)
                continue

            consecutive_failures = 0
            elapsed = time.monotonic() - start
            data = _build_sample(home, elapsed, phase)
            curr_power = data["total_power_w"]

            if prev_power is not None and elapsed > prev_elapsed:
                energy_computed = _compute_energy(
                    prev_power, curr_power, elapsed - prev_elapsed, energy_computed,
                )

            data["energy_computed_wh"] = round(energy_computed, 2)
            _write_csv_row(writer, data)
            csv_file.flush()
            _display_status(data, sample, start)

            for w in _check_warnings(data):
                click.secho(f"  ⚠  {w}", fg="yellow")

            prev_power = curr_power
            prev_elapsed = elapsed
            sample += 1

            soc = data.get("soc_pct")
            if isinstance(soc, (int, float)) and soc <= 0:
                click.secho("\nSOC reached 0% — test complete!", fg="green")
                break

            await asyncio.sleep(interval)

    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        click.echo()
        csv_file.close()
        try:
            await client.disconnect()
        except Exception:
            pass

    _print_summary(start, sample, energy_computed, data, output_path)


# ═══════════════════════════════════════════════════════════════════════
#  Pure functions (testable without BLE)
# ═══════════════════════════════════════════════════════════════════════


def _compute_energy(prev_power, curr_power, delta_seconds, prev_energy):
    """Trapezoidal integration: avg power × Δt in hours → watt-hours."""
    avg_power = (prev_power + curr_power) / 2.0
    energy_added = avg_power * delta_seconds / 3600.0
    return prev_energy + energy_added


def _soc_bar(pct, width=SOC_BAR_WIDTH):
    """ASCII progress bar: ████████████░░░░░░░░"""
    if not isinstance(pct, (int, float)):
        return "░" * width
    pct = max(0, min(100, pct))
    filled = int(round(pct * width / 100.0))
    return "█" * filled + "░" * (width - filled)


def _build_sample(home, elapsed_seconds, phase=""):
    """Build a flat dict from parsed BLE data + elapsed time."""
    dc_power = home.get("totalDCPower", 0) or 0
    ac_power = abs(home.get("totalACPower", 0) or 0)
    soc = home.get("packTotalSoc")
    grid_power = abs(home.get("totalGridPower", 0) or 0)
    pv_power = home.get("totalPVPower", 0) or 0

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(elapsed_seconds, 1),
        "soc_pct": soc if soc is not None else "",
        "pack_v": home.get("packTotalVoltage", ""),
        "pack_a": home.get("packTotalCurrent", ""),
        "dc_power_w": dc_power,
        "ac_power_w": ac_power,
        "total_power_w": dc_power + ac_power,
        "pv_power_w": pv_power if pv_power is not None else "",
        "grid_power_w": grid_power if grid_power is not None else "",
        "charging_status": STATUS_MAP.get(home.get("packChargingStatus"), ""),
        "est_remaining_min": home.get("packDsgEmptyTime", ""),
        "ambient_temp_c": home.get("ambientTemp", ""),
        "inv_temp_c": home.get("invMaxTemp", ""),
        "energy_computed_wh": 0.0,
        "energy_register_wh": home.get("totalDCEnergy", ""),
        "phase": phase or "",
    }


def _check_prerequisites(home):
    """Return list of warning strings; empty list = all clear."""
    warnings = []
    soc = home.get("packTotalSoc")
    if soc is None or soc < PRE_CHECK_SOC_MIN:
        warnings.append(
            f"SOC is {soc}% (need ≥ {PRE_CHECK_SOC_MIN}%). Charge the device first."
        )
    grid = abs(home.get("totalGridPower", 0) or 0)
    if grid > PRE_CHECK_GRID_MAX:
        warnings.append(
            f"Grid power is {grid}W (must be ≤ {PRE_CHECK_GRID_MAX}W). Disconnect shore power."
        )
    pv = home.get("totalPVPower", 0) or 0
    if pv > PRE_CHECK_PV_MAX:
        warnings.append(
            f"PV power is {pv}W (must be ≤ {PRE_CHECK_PV_MAX}W). Disconnect solar panels."
        )
    return warnings


def _check_warnings(data):
    """Return list of runtime warning strings."""
    warnings = []
    grid = data.get("grid_power_w", 0) or 0
    if grid > GRID_WARNING_W:
        warnings.append(f"Grid input active — {grid}W (charging detected)")
    pv = data.get("pv_power_w", 0) or 0
    if pv > PV_WARNING_W:
        warnings.append(f"PV input active — {pv}W (charging detected)")
    return warnings


# ═══════════════════════════════════════════════════════════════════════
#  CSV output
# ═══════════════════════════════════════════════════════════════════════


def _write_csv_header(writer, device, phase, expected_load, interval):
    """Write comment header block + column names to an open CSV writer."""
    writer.writerow(["# bluetti-cli load test"])
    writer.writerow([f"# Device: {device.type}-{device.sn}"])
    if phase:
        writer.writerow([f"# Phase: {phase}"])
    if expected_load:
        writer.writerow([f"# Expected load: {expected_load} W"])
    writer.writerow([f"# Interval: {interval} s"])
    writer.writerow([f"# Started: {datetime.now(timezone.utc).isoformat()}"])
    writer.writerow(["#"])
    writer.writerow(CSV_COLUMNS)


def _write_csv_row(writer, data):
    """Write one data row, mapping dict keys to CSV_COLUMNS order."""
    row = []
    for col in CSV_COLUMNS:
        val = data.get(col, "")
        row.append("" if val in (None, "") else str(val))
    writer.writerow(row)


# ═══════════════════════════════════════════════════════════════════════
#  Terminal display
# ═══════════════════════════════════════════════════════════════════════


def _display_status(data, sample_n, start_time):
    """Print current load-test status to the terminal."""
    elapsed = data.get("elapsed_s", 0)
    hours = int(elapsed // 3600)
    minutes = int((elapsed % 3600) // 60)
    seconds = int(elapsed % 60)
    soc = data.get("soc_pct", 0)
    phase = data.get("phase", "")

    click.echo("─" * 60)
    header = f"  Load Test"
    if phase:
        header += f" | {phase}"
    header += f" | Sample {sample_n} | {hours}h {minutes:02d}m {seconds:02d}s"
    click.echo(header)
    click.echo("─" * 60)
    click.echo(
        f"  SOC:       {soc:>3}% {_soc_bar(soc)}"
    )
    click.echo(
        f"  Load:      {data.get('ac_power_w', 0)} W (AC)  |  "
        f"{data.get('dc_power_w', 0)} W (DC)  |  "
        f"{data.get('total_power_w', 0)} W total"
    )
    pack_v = data.get("pack_v", "")
    pack_a = data.get("pack_a", "")
    click.echo(
        f"  Pack:      {pack_v if pack_v != '' else '--'} V  |  "
        f"{pack_a if pack_a != '' else '--'} A"
    )
    amb = data.get("ambient_temp_c", "")
    inv = data.get("inv_temp_c", "")
    click.echo(
        f"  Temp:      {amb if amb != '' else '--'}°C amb  |  "
        f"{inv if inv != '' else '--'}°C inv"
    )
    click.echo(f"  ────────────────────────────────────────────")
    click.echo(f"  Energy (computed):    {data.get('energy_computed_wh', 0):.1f} Wh")
    click.echo(f"  Energy (register):    {data.get('energy_register_wh', '--')} Wh")
    est = data.get("est_remaining_min", "")
    if est != "":
        click.echo(f"  Est. remaining:       {est} min")
    pv = data.get("pv_power_w", 0) or 0
    grid = data.get("grid_power_w", 0) or 0
    click.echo(f"  PV: {pv} W  |  Grid: {grid} W")


def _print_summary(start_time, sample_count, energy_computed, final_data, output_path):
    """Print post-test summary to the terminal."""
    elapsed = time.monotonic() - start_time
    hours = int(elapsed // 3600)
    minutes = int((elapsed % 3600) // 60)

    click.echo("─" * 60)
    click.echo(f"  Load Test Complete — {hours}h {minutes}m elapsed")
    click.echo("─" * 60)
    click.echo(f"  Samples:                    {sample_count}")
    click.echo(f"  Start SOC:                  {final_data.get('soc_pct', '?')}%")
    click.echo(f"  Energy (computed):          {energy_computed:.1f} Wh")
    reg = final_data.get("energy_register_wh", "")
    click.echo(f"  Energy (register final):    {reg if reg != '' else 'N/A'} Wh")
    click.echo(f"  Avg load:                   {final_data.get('total_power_w', 0):.0f} W")
    pack_v = final_data.get("pack_v", "")
    if pack_v != "":
        click.echo(f"  Final pack voltage:         {pack_v} V")
    click.echo(f"  CSV:  {output_path}")


# ═══════════════════════════════════════════════════════════════════════
#  Async BLE helpers
# ═══════════════════════════════════════════════════════════════════════


async def _verify_prerequisites(client, device):
    """Read home data and verify SOC ≥ 95%, no grid/PV input.

    Prompts user to press Enter before reading.
    """
    click.echo(
        "\nConnect the load and disconnect all charging sources, then press Enter."
    )
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        click.echo()
        return False

    cmd1 = ReadHoldingRegisters(100, 6)
    raw1 = await client.execute(cmd1)
    home = device.parse(100, raw1)

    cmd2 = ReadHoldingRegisters(140, 10)
    raw2 = await client.execute(cmd2)
    home.update(device.parse(140, raw2))

    warnings = _check_prerequisites(home)
    if warnings:
        click.echo()
        for w in warnings:
            click.secho(f"  ✗ {w}", fg="red")
        return False
    return True


async def _read_home(client, device):
    """Execute 3 BLE reads and return parsed home dict.

    Raises on complete failure (can't read basic home data).
    Gracefully skips power/temp reads on ModbusError.
    """
    cmd1 = ReadHoldingRegisters(100, 6)
    raw1 = await client.execute(cmd1)
    home = device.parse(100, raw1)

    try:
        cmd2 = ReadHoldingRegisters(140, 19)
        raw2 = await client.execute(cmd2)
        home.update(device.parse(140, raw2))
    except ModbusError:
        pass

    try:
        cmd3 = ReadHoldingRegisters(1151, 2)
        raw3 = await client.execute(cmd3)
        home.update(device.parse(1151, raw3))
    except ModbusError:
        pass

    return home

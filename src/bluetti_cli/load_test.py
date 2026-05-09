# ABOUTME: Load test mode — coached discharge test with CSV logging and dual energy tracking.

import asyncio
import csv
import time
from datetime import datetime, timezone

import click

from .bluetooth.client import BluetoothClient
from .bluetooth.exc import ModbusError
from .core.commands import ReadHoldingRegisters

MIN_INTERVAL = 15
GRID_WARNING_W = 10
PV_WARNING_W = 10
PRE_CHECK_SOC_MIN = 95
PRE_CHECK_GRID_MAX = 5
PRE_CHECK_PV_MAX = 5
MAX_BLE_RETRIES = 3

CSV_COLUMNS = [
    "timestamp",
    "elapsed_s",
    "soc_pct",
    "pack_v",
    "pack_a",
    "dc_power_w",
    "ac_power_w",
    "total_power_w",
    "pv_power_w",
    "grid_power_w",
    "charging_status",
    "est_remaining_min",
    "ambient_temp_c",
    "inv_temp_c",
    "energy_computed_wh",
    "energy_register_wh",
    "phase",
]

STATUS_MAP = {0: "Idle", 1: "Charging", 2: "Discharging", 3: "Floating"}

SOC_BAR_WIDTH = 20


# ═══════════════════════════════════════════════════════════════════════
#  Public entry point (called from cli.py)
# ═══════════════════════════════════════════════════════════════════════


async def run_load_test(device, output_path, interval, expected_load, phase, *, encrypted: bool = False):
    """Run a full load-test cycle: coach → verify → poll → CSV → summary."""
    client = BluetoothClient(device.address, encrypted=encrypted)
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
                    prev_power,
                    curr_power,
                    elapsed - prev_elapsed,
                    energy_computed,
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
        # Task was cancelled — exit cleanly via finally block.
        pass
    except KeyboardInterrupt:
        # User pressed Ctrl-C — exit cleanly via finally block.
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


def _none_to_empty(val):
    """Convert None to empty string; pass through everything else."""
    return "" if val is None else val


def _build_sample(home, elapsed_seconds, phase=""):
    """Build a flat dict from parsed BLE data + elapsed time."""
    dc_power = home.get("totalDCPower", 0) or 0
    ac_power = abs(home.get("totalACPower", 0) or 0)
    soc = home.get("packTotalSoc")
    grid_power = abs(home.get("totalGridPower", 0) or 0)
    pv_power = home.get("totalPVPower", 0) or 0

    raw_time = home.get("packDsgEmptyTime")
    if raw_time is None or raw_time == "":
        est_min = ""
    else:
        est_min = raw_time * 6

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
        "est_remaining_min": est_min,
        "ambient_temp_c": _none_to_empty(home.get("ambientTemp")),
        "inv_temp_c": _none_to_empty(home.get("invMaxTemp")),
        "energy_computed_wh": 0.0,
        "energy_register_wh": home.get("totalDCEnergy", ""),
        "phase": phase or "",
    }


def _check_prerequisites(home):
    """Return list of warning strings; empty list = all clear."""
    warnings = []
    soc = home.get("packTotalSoc")
    if soc is None or soc < PRE_CHECK_SOC_MIN:
        warnings.append(f"SOC is {soc}% (need ≥ {PRE_CHECK_SOC_MIN}%). Charge the device first.")
    grid = abs(home.get("totalGridPower", 0) or 0)
    if grid > PRE_CHECK_GRID_MAX:
        warnings.append(f"Grid power is {grid}W (must be ≤ {PRE_CHECK_GRID_MAX}W). Disconnect shore power.")
    pv = home.get("totalPVPower", 0) or 0
    if pv > PRE_CHECK_PV_MAX:
        warnings.append(f"PV power is {pv}W (must be ≤ {PRE_CHECK_PV_MAX}W). Disconnect solar panels.")
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
    header = "  Load Test"
    if phase:
        header += f" | {phase}"
    header += f" | Sample {sample_n} | {hours}h {minutes:02d}m {seconds:02d}s"
    click.echo(header)
    click.echo("─" * 60)
    click.echo(f"  SOC:       {soc:>3}% {_soc_bar(soc)}")
    click.echo(
        f"  Load:      {data.get('ac_power_w', 0)} W (AC)  |  "
        f"{data.get('dc_power_w', 0)} W (DC)  |  "
        f"{data.get('total_power_w', 0)} W total"
    )
    pack_v = data.get("pack_v", "")
    pack_a = data.get("pack_a", "")
    click.echo(f"  Pack:      {pack_v if pack_v != '' else '--'} V  |  {pack_a if pack_a != '' else '--'} A")
    amb = data.get("ambient_temp_c", "")
    inv = data.get("inv_temp_c", "")
    click.echo(f"  Temp:      {amb if amb != '' else 'Not fitted'}  |  {inv if inv != '' else 'Not fitted'}")
    click.echo("  ────────────────────────────────────────────")
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

    analysis = _analyze_csv(output_path)
    if analysis:
        click.echo(f"  Measured capacity:          {analysis['capacity_wh']:.0f} Wh")
        reg_delta = analysis.get("register_delta_wh")
        if reg_delta is not None:
            pct = abs(analysis["capacity_wh"] - reg_delta) / analysis["capacity_wh"] * 100
            click.echo(
                f"  Register energy delta:      {reg_delta:.0f} Wh  "
                f"({pct:.1f}% {'above' if reg_delta > analysis['capacity_wh'] else 'below'} computed)"
            )
        eff = analysis.get("efficiency_pct")
        if eff is not None:
            click.echo(f"  Avg efficiency:             {eff:.1f}%")
        click.echo(f"  Avg load:                   {analysis.get('avg_load_w', 0):.0f} W")
        peak = analysis.get("peak_load_w", 0)
        if peak:
            click.echo(f"  Peak load:                  {peak:.0f} W")

        voltages = analysis.get("voltage_at_soc", {})
        if voltages:
            click.echo(f"\n  {click.style('Pack voltage at SOC milestones:', bold=True)}")
            for soc_label in ("100%", "75%", "50%", "25%", "0%"):
                v = voltages.get(soc_label)
                if v is not None:
                    click.echo(f"    {soc_label:<6s}  {v:>5.1f} V")

        bms = analysis.get("bms_accuracy")
        if bms is not None:
            click.echo(
                f"\n  BMS estimate at 50% SOC:     {bms:.0f} min  "
                f"(actual: {analysis.get('actual_remaining_at_50pct', 0):.0f} min)"
            )

        max_amb = analysis.get("max_ambient_c")
        max_inv = analysis.get("max_inverter_c")
        if max_amb is not None or max_inv is not None:
            parts = []
            if max_amb is not None:
                parts.append(f"amb {max_amb}°C")
            if max_inv is not None:
                parts.append(f"inv {max_inv}°C")
            click.echo(f"  Max temps:                  {', '.join(parts)}")
    else:
        click.echo(f"  Energy (computed):          {energy_computed:.1f} Wh")
        click.echo(f"  Avg load:                   {final_data.get('total_power_w', 0):.0f} W")

    click.echo(f"  CSV:  {output_path}")


def _analyze_csv(output_path):
    """Read the CSV and return a dict of computed statistics, or None if too few rows."""
    rows = []
    with open(output_path, "r", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            rows.append(row)

    if len(rows) < 5:
        return None

    header = rows[0]
    data_rows = rows[1:]

    if len(data_rows) < 5:
        return None

    def col(name):
        try:
            return header.index(name)
        except ValueError:
            return None

    idx_elapsed = col("elapsed_s")
    idx_soc = col("soc_pct")
    idx_pack_v = col("pack_v")
    idx_pack_a = col("pack_a")
    idx_total_p = col("total_power_w")
    idx_energy_c = col("energy_computed_wh")
    idx_energy_r = col("energy_register_wh")
    idx_est = col("est_remaining_min")
    idx_amb = col("ambient_temp_c")
    idx_inv = col("inv_temp_c")

    def float_val(row, idx):
        try:
            v = row[idx].strip()
            return float(v) if v else None
        except (IndexError, ValueError):
            return None

    def int_val(row, idx):
        try:
            v = row[idx].strip()
            return int(float(v)) if v else None
        except (IndexError, ValueError):
            return None

    # --- Capacity ---
    capacity_wh = float_val(data_rows[-1], idx_energy_c) if idx_energy_c is not None else None

    # --- Register energy delta ---
    register_delta = None
    if idx_energy_r is not None:
        first_reg = float_val(data_rows[0], idx_energy_r)
        last_reg = float_val(data_rows[-1], idx_energy_r)
        if first_reg is not None and last_reg is not None:
            register_delta = last_reg - first_reg

    # --- Load stats ---
    total_powers = []
    pack_powers = []
    for row in data_rows:
        tp = float_val(row, idx_total_p) if idx_total_p is not None else None
        if tp is not None:
            total_powers.append(tp)
        pv = float_val(row, idx_pack_v) if idx_pack_v is not None else None
        pa = float_val(row, idx_pack_a) if idx_pack_a is not None else None
        if pv is not None and pa is not None:
            pack_powers.append(pv * pa)

    avg_load_w = sum(total_powers) / len(total_powers) if total_powers else 0
    peak_load_w = max(total_powers) if total_powers else 0

    # --- Efficiency ---
    efficiency_pct = None
    if pack_powers and total_powers:
        avg_pack = sum(pack_powers) / len(pack_powers)
        avg_out = sum(total_powers) / len(total_powers)
        if avg_pack > 0:
            efficiency_pct = avg_out / avg_pack * 100

    # --- Voltage at SOC milestones ---
    voltage_at_soc = {}
    if idx_soc is not None and idx_pack_v is not None:
        targets = {100: "100%", 90: "90%", 75: "75%", 50: "50%", 25: "25%", 0: "0%"}
        for row in data_rows:
            soc = int_val(row, idx_soc)
            v = float_val(row, idx_pack_v)
            if soc is None or v is None:
                continue
            for target, label in list(targets.items()):
                if soc <= target and label not in voltage_at_soc:
                    voltage_at_soc[label] = v
                    del targets[target]

    # --- BMS accuracy at 50% SOC ---
    bms_accuracy = None
    actual_remaining_at_50 = None
    if idx_soc is not None and idx_est is not None and idx_elapsed is not None:
        total_runtime = float_val(data_rows[-1], idx_elapsed)
        for row in data_rows:
            soc = int_val(row, idx_soc)
            est = float_val(row, idx_est)
            elapsed = float_val(row, idx_elapsed)
            if soc is not None and soc <= 50 and est is not None and elapsed is not None:
                bms_accuracy = est
                if total_runtime is not None:
                    actual_remaining_at_50 = (total_runtime - elapsed) / 60.0
                break

    # --- Max temps ---
    max_amb = None
    max_inv = None
    if idx_amb is not None:
        for row in data_rows:
            v = float_val(row, idx_amb)
            if v is not None and (max_amb is None or v > max_amb):
                max_amb = v
    if idx_inv is not None:
        for row in data_rows:
            v = float_val(row, idx_inv)
            if v is not None and (max_inv is None or v > max_inv):
                max_inv = v

    return {
        "capacity_wh": capacity_wh or 0,
        "register_delta_wh": register_delta,
        "avg_load_w": avg_load_w,
        "peak_load_w": peak_load_w,
        "efficiency_pct": efficiency_pct,
        "voltage_at_soc": voltage_at_soc,
        "bms_accuracy": bms_accuracy,
        "actual_remaining_at_50pct": actual_remaining_at_50,
        "max_ambient_c": max_amb,
        "max_inverter_c": max_inv,
    }


# ═══════════════════════════════════════════════════════════════════════
#  Async BLE helpers
# ═══════════════════════════════════════════════════════════════════════


async def _verify_prerequisites(client, device):
    """Read home data and verify SOC ≥ 95%, no grid/PV input.

    Prompts user to press Enter before reading.
    """
    click.echo("\nConnect the load and disconnect all charging sources, then press Enter.")
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
        cmd2 = ReadHoldingRegisters(140, 10)
        raw2 = await client.execute(cmd2)
        home.update(device.parse(140, raw2))
    except ModbusError:
        pass

    try:
        cmd2b = ReadHoldingRegisters(150, 9)
        raw2b = await client.execute(cmd2b)
        home.update(device.parse(150, raw2b))
    except ModbusError:
        pass

    try:
        cmd3 = ReadHoldingRegisters(1151, 2)
        raw3 = await client.execute(cmd3)
        home.update(device.parse(1151, raw3))
    except ModbusError:
        pass

    return home

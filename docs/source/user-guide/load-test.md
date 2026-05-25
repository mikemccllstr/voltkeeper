# Load Test

Run a controlled battery discharge test.

```bash
voltkeeper load-test AA:BB:CC:DD:EE:FF -l 500 -p "500W heater on AC"
```

The test will:

1. Prompt you to fully charge, connect a load, and disconnect charging
2. Verify prerequisites (SOC >= 95%, no grid/PV input)
3. Poll every N seconds — logging SOC, voltage, current, AC/DC/PV/grid power,
   temperatures, device time estimate, and energy measurements
4. Warn if grid or PV charging is detected (> 10 W)
5. End when SOC reaches 0%, BLE connection drops, or you press Ctrl-C
6. Print a summary with capacity, average load, min voltage, and max temp

## Options

| Option | Description |
|---|---|
| `-o, --output PATH` | CSV output file (default: `ac2a_load_test_YYYYMMDD_HHMMSS.csv`) |
| `-i, --interval SECONDS` | Sample interval, minimum 15s (default: 60) |
| `-l, --expected-load W` | Known load wattage for analysis reference |
| `-p, --phase TEXT` | Label for this test phase (useful for multi-phase testing) |

## CSV Output

The default output filename (`ac2a_load_test_YYYYMMDD_HHMMSS.csv`) is hardcoded
for the AC2A; use `-o` to specify a custom path for other devices.

The file has a comment header block (lines beginning with `#`) followed by a row
of column names. Empty cells indicate failed BLE reads and are Excel-friendly.

| Column | Description |
|---|---|
| `timestamp` | ISO 8601 UTC timestamp of the sample |
| `elapsed_s` | Seconds elapsed since test start |
| `soc_pct` | Battery state of charge (%) |
| `pack_v` | Battery pack voltage (V) |
| `pack_a` | Battery pack current (A) |
| `dc_power_w` | DC output power (W) |
| `ac_power_w` | AC output power (W) |
| `total_power_w` | Total output power (W) |
| `pv_power_w` | Solar input power (W) |
| `grid_power_w` | Grid/AC-in power (W) |
| `charging_status` | Charging state (Idle, Charging, Discharging, Floating) |
| `est_remaining_min` | Device-estimated time remaining (minutes) |
| `ambient_temp_c` | Ambient temperature (°C) |
| `inv_temp_c` | Inverter temperature (°C) |
| `energy_computed_wh` | Cumulative Wh by trapezoidal integration |
| `energy_register_wh` | Cumulative Wh from device's `totalDCEnergy` register |
| `phase` | Phase label passed via `--phase` |

## Energy Measurements

Two energy measurements are logged:

- **Computed** — trapezoidal integration of measured power over time
- **Register** — the device's own `totalDCEnergy` register (for validation)

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

The CSV has 17 columns with a comment header block; empty cells for failed
BLE reads are Excel-friendly.

## Energy Measurements

Two energy measurements are logged:

- **Computed** — trapezoidal integration of measured power over time
- **Register** — the device's own `totalDCEnergy` register (for validation)

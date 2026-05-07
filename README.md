# bluetti-cli

CLI tool for Bluetti power stations — scan, connect, and read battery data over BLE.

## Install

### Quick run (no clone required)

```bash
uvx --from git+https://github.com/mikemccllstr/bluetti-apk-reverse bluetti-cli --help
```

This downloads and runs the tool in an isolated environment. Replace `--help` with any
command or subcommand.

### From source

```bash
git clone https://github.com/mikemccllstr/bluetti-apk-reverse
cd bluetti-apk-reverse
uv run bluetti-cli --help
```

## Usage

### Scan for devices

```bash
bluetti-cli scan
```

Displays all nearby Bluetti devices and shows the exact command to connect to each one.

Options:
- `-t, --timeout FLOAT`  Scan timeout in seconds (default: 10.0)

### Read battery status

```bash
bluetti-cli status                  # auto-scan for devices, then pick one
bluetti-cli status AA:BB:CC:DD:EE:FF  # connect directly
```

Output:
- Battery SOC (%)
- Pack voltage
- Charging status
- Time to full / time to empty (context-dependent)
- DC load, AC load, and total load (watts)

Options:
- `-t, --timeout FLOAT`  Scan timeout in seconds (default: 10.0, used only when no address given)
- `-v, --verbose`         Display all available device information (power meters, energy totals, PV strings, grid, loads, temperatures, software versions, writable controls, and device capabilities)

### Write device settings

```bash
bluetti-cli write AA:BB:CC:DD:EE:FF ac_output on
bluetti-cli write AA:BB:CC:DD:EE:FF dc_output off
bluetti-cli write AA:BB:CC:DD:EE:FF charging_mode turbo
```

Writable fields (see `--verbose` output for current values):
- **switches:** `ac_output`, `dc_output`, `power_off`, `dc_eco_mode`, `ac_eco_mode`, `power_lifting`, `alarm_sound`  — `on`/`off`
- `charging_mode`  — `standard`/`turbo`/`silent`
- **numeric:** `battery_range_start`, `battery_range_end`, `lcd_timeout`, `led_color`, `soc_low`, `soc_high`, `inv_voltage`, `inv_freq`, `working_mode`

### MQTT bridge

```bash
bluetti-cli mqtt AA:BB:CC:DD:EE:FF --broker 192.168.1.100
```

Continuously polls the device and publishes state to an MQTT broker.
Supports Home Assistant MQTT auto-discovery (on by default).

Options:
- `--broker TEXT`         MQTT broker hostname (required)
- `--port INTEGER`        MQTT broker port (default: 1883)
- `--username TEXT`       MQTT broker username
- `--password TEXT`       MQTT broker password
- `--interval INTEGER`    Seconds between polling cycles (default: 0 = as fast as possible)
- `--ha-config MODE`      Home Assistant discovery mode: `normal`, `none`, `advanced` (default: normal)
- `--restart-on-source-change`  Exit cleanly when source code changes, so systemd restarts the process

Use `--restart-on-source-change` when running under systemd to automatically
pick up code changes (pairs with `Restart=always` in the generated unit file).

To verify published messages in another terminal:
```bash
mosquitto_sub -t 'bluetti/state/#' -v
```

### Load test

```bash
bluetti-cli load-test [OPTIONS] ADDRESS
```

Runs a controlled battery discharge test. Coaches you through setup,
then logs device stats every N seconds to a CSV file until the battery
reaches 0%.

Options:
- `-o, --output PATH`        CSV output file (default: `ac2a_load_test_YYYYMMDD_HHMMSS.csv`)
- `-i, --interval SECONDS`   Sample interval, minimum 15s (default: 60)
- `-l, --expected-load W`    Known load wattage for analysis reference
- `-p, --phase TEXT`         Label for this test phase (useful for multi-phase testing)

Example:
```bash
bluetti-cli load-test AA:BB:CC:DD:EE:FF -l 500 -p "500W heater on AC"
```

The test will:
1. Prompt you to fully charge, connect a load, and disconnect charging
2. Verify prerequisites (SOC ≥ 95%, no grid/PV input)
3. Poll every N seconds — logging SOC, voltage, current, AC/DC/PV/grid power,
   temperatures, device time estimate, and two energy measurements:
   - **Computed** — trapezoidal integration of measured power × time
   - **Register** — the device's own `totalDCEnergy` register (for validation)
4. Warn if grid or PV charging is detected (> 10 W)
5. End when SOC reaches 0%, BLE connection drops, or you press Ctrl-C
6. Print a summary with capacity, average load, min voltage, and max temp

The CSV has 17 columns with a comment header block; empty cells for failed
BLE reads are Excel-friendly.

### Generate systemd service

```bash
bluetti-cli generate-service AA:BB:CC:DD:EE:FF --broker 192.168.1.100
```

Generates a systemd unit file to run the MQTT bridge as a persistent
service. Prints to stdout; use `-o FILE` to write directly.

Options mirror the `mqtt` command: `--port`, `--username`, `--password`,
`--interval`, `--ha-config`. Additional options:

- `--user NAME`    System user to run as (default: current user)
- `--exec PATH`    Path to `bluetti-cli` executable (default: auto-detect)
- `-o, --output PATH`  Write to file instead of stdout

Install the generated file:
```bash
sudo cp bluetti-mqtt-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bluetti-mqtt-*.service
```

### Help

```bash
bluetti-cli --help
bluetti-cli status --help
bluetti-cli scan --help
bluetti-cli load-test --help
bluetti-cli --version
```

## Requirements

- Python 3.13+
- Linux with BlueZ (BLE support)
- Bluetooth adapter with scan capability (`CAP_NET_ADMIN` or run with `sudo`)

The tool reads plain Modbus RTU over BLE from Bluetti AC2A power stations.
Encrypted ESP32 devices are not yet supported.

## Testing

```bash
uv run pytest                 # unit tests (fast, no BLE required)
uv run pytest -m integration  # integration tests (requires BLE adapter)
```

## Development

See [docs/FINDINGS.md](docs/FINDINGS.md) for reverse-engineering notes and protocol details helpful when enhancing this tool.
```

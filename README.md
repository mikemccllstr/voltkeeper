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
- Pack voltage and current
- Charging status
- Time to full / time to empty

Options:
- `-t, --timeout FLOAT`  Scan timeout in seconds (default: 10.0, used only when no address given)
- `-v, --verbose`         Display all available device information (power meters, energy totals, PV strings, grid, loads, temperatures, software versions)

### Help

```bash
bluetti-cli --help
bluetti-cli status --help
bluetti-cli scan --help
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

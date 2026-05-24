# User Guide

```{toctree}
:hidden:

scan
status
write
mqtt
load-test
probe-annotate
systemd
```

voltkeeper is a cross-platform command-line tool for Bluetti power stations.
It scans, connects, reads battery data, writes device settings, publishes to
MQTT, and runs load tests — all over local BLE, with no cloud account required.

## Install

### Quick run (no clone required)

```bash
uvx --from git+https://github.com/mikemccllstr/voltkeeper voltkeeper --help
```

This downloads and runs the tool in an isolated environment.

### From source

```bash
git clone https://github.com/mikemccllstr/voltkeeper
cd voltkeeper
uv run voltkeeper --help
```

## Requirements

- Python 3.13+
- Linux with BlueZ, macOS 11+, or Windows 10 build 19041+ (BLE support)
- Bluetooth adapter with scan capability

On Linux, the BLE adapter may require elevated privileges (`CAP_NET_ADMIN` or
`sudo`). On macOS, the device's BLE MAC address may be reported as a UUID
rather than a hardware address — use the UUID directly.

The tool reads plain Modbus RTU over BLE from Bluetti power stations.
Encrypted devices (AES-CBC over BLE) are supported; the handshake is handled
automatically.

## Development

Run the full quality gate before committing:

```bash
mise run check
```

This runs lint, typecheck, and tests. See the [Developer Guide](../developer/index.md)
for contributing and adding new devices.

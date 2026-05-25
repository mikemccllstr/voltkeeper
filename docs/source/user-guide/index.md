# User Guide

```{toctree}
:hidden:

scan
status
write
mqtt
daemon
load-test
probe-annotate
systemd
```

voltkeeper is a cross-platform command-line tool for Bluetti power stations.
It scans, connects, reads battery data, writes device settings, publishes to
MQTT, and runs load tests — all over local BLE, with no cloud account required.

## Install

```bash
pip install voltkeeper
```

### Quick run (no install required)

```bash
uvx --from git+https://github.com/mikemccllstr/voltkeeper voltkeeper --help
```

This downloads and runs the tool in an isolated environment without installing it.

### From source

```bash
git clone https://github.com/mikemccllstr/voltkeeper
cd voltkeeper
uv run voltkeeper --help
```

## Requirements

- Python 3.10+
- Linux with BlueZ, macOS 11+, or Windows 10 build 19041+ (BLE support)
- Bluetooth adapter with scan capability

On Linux, the BLE adapter may require elevated privileges (`CAP_NET_ADMIN` or
`sudo`). On macOS, the device's BLE MAC address may be reported as a UUID
rather than a hardware address — use the UUID directly.

The tool reads plain Modbus RTU over BLE from Bluetti power stations.
Encrypted devices (AES-CBC over BLE) are supported; the handshake is handled
automatically.

See the [Developer Guide](../developer/index.md) for contributing and adding new devices.

<img src="https://raw.githubusercontent.com/mikemccllstr/voltkeeper/main/docs/voltkeeper-wordmark.svg" alt="voltkeeper" height="60">

[![PyPI version](https://img.shields.io/pypi/v/voltkeeper.svg)](https://pypi.org/project/voltkeeper/)
[![Python versions](https://img.shields.io/pypi/pyversions/voltkeeper.svg)](https://pypi.org/project/voltkeeper/)
[![CI](https://github.com/mikemccllstr/voltkeeper/actions/workflows/ci.yml/badge.svg)](https://github.com/mikemccllstr/voltkeeper/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/voltkeeper.svg)](https://github.com/mikemccllstr/voltkeeper/blob/main/LICENSE)

CLI tool for Bluetti power stations — scan, connect, and control over local BLE. No cloud account required.

## Why voltkeeper?

- **Local-first, offline control** — talk directly to your power station over Bluetooth. No internet connection, no cloud account, no vendor API.
- **Your hardware, your data** — nothing leaves your local network unless you choose to publish it to MQTT.
- **Cross-platform** — runs on Linux, macOS, and Windows with a BLE adapter.
- **Home Assistant ready** — built-in MQTT auto-discovery publishes device state to your Home Assistant dashboard.

<!-- TODO: add terminal recording screenshot -->
<!-- ![voltkeeper demo](docs/demo.svg) -->

## Quick demo

```bash
voltkeeper scan                          # discover nearby Bluetti devices
voltkeeper status                        # auto-detects device, shows battery SOC and load
voltkeeper write AA:BB:CC:DD:EE:FF ac_output on   # toggle AC output
```

## Capabilities

| Command | What it does |
|---|---|
| `scan` | Discover nearby Bluetti devices and show exact connect commands |
| `status` | Read battery SOC, pack voltage, load, and charging status |
| `write` | Toggle AC/DC output, change charging mode, adjust device settings |
| `mqtt-publish` | Stream device telemetry to MQTT with Home Assistant auto-discovery |
| `mqtt-listen` | Watch battery SOC over MQTT and shut down host on low battery |
| `load-test` | Run a controlled battery discharge test with CSV logging |
| `probe` | Sweep register blocks for reverse-engineering device support |
| `annotate` | Live-poll and interactively label register fields |
| `mqtt-publish-service` | Generate systemd unit file for MQTT publishing |
| `mqtt-listen-service` | Generate systemd unit file for MQTT listen watchdog |
| `daemon` | Start/manage a persistent background service with HTTP API and Web UI |

See the [User Guide](https://mikemccllstr.github.io/voltkeeper/user-guide/) for full command reference, or run `voltkeeper <command> --help`.

## Install

```bash
pip install voltkeeper
```

Or try it without installing:

```bash
uvx --from git+https://github.com/mikemccllstr/voltkeeper voltkeeper --help
```

Or from source:

```bash
git clone https://github.com/mikemccllstr/voltkeeper
cd voltkeeper
uv run voltkeeper --help
```

## Requirements

- Python 3.10+
- Linux with BlueZ, macOS 11+, or Windows 10 build 19041+ (BLE support)
- Bluetooth adapter with scan capability

On Linux, the BLE adapter may require elevated privileges (`CAP_NET_ADMIN` or `sudo`). Encrypted Bluetti devices (AES-CBC over BLE) are supported — the handshake is handled automatically.

## Daemon (long-running service)

For monitoring multiple devices simultaneously, a persistent Web UI, or avoiding repeated BLE scans, run `voltkeeperd` as a background service.

**Config file** — create `~/.config/voltkeeper/config.yaml`:

```yaml
server:
  api_key: "your-secret-key"

devices:
  - address: "AA:BB:CC:DD:EE:FF"
    name: "Living Room AC2A"

scan:
  interval: 60       # seconds between reconciliation scans
  timeout: 10.0      # BLE scan timeout
```

Config is searched in order: `./voltkeeper.yaml`, `~/.config/voltkeeper/config.yaml`, `/etc/voltkeeper/config.yaml`.

**Start the daemon:**

```bash
voltkeeper daemon start          # runs in foreground
```

**Query the daemon from the CLI:**

```bash
voltkeeper status --daemon localhost           # show all devices
voltkeeper status AA:BB:CC:DD:EE:FF --daemon localhost   # single device detail
voltkeeper write AA:BB:CC:DD:EE:FF ac_output on --daemon localhost
```

**Web UI** — open `http://localhost:8080` in a browser. Enter your API key when prompted.

**Systemd unit** (for production use):

```ini
[Unit]
Description=voltkeeperd
After=bluetooth.target network.target

[Service]
ExecStart=/usr/bin/voltkeeperd
Restart=always
RestartSec=30
User=your-user
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Save as `/etc/systemd/system/voltkeeperd.service`, then `systemctl enable --now voltkeeperd`.

The daemon can also be secured with network ACLs by adding to `server.allowed_networks`:

```yaml
server:
  api_key: "your-secret-key"
  allowed_networks: ["192.168.1.0/24", "127.0.0.0/8"]
```

## Links

- [Documentation](https://mikemccllstr.github.io/voltkeeper/)
- [Contributing a new device](https://mikemccllstr.github.io/voltkeeper/developer/contributing-devices/)
- [Issue tracker](https://github.com/mikemccllstr/voltkeeper/issues)

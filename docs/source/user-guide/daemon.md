# Daemon

For monitoring multiple devices simultaneously, a persistent Web UI, or
avoiding repeated BLE scans on every command, run `voltkeeperd` as a
background service.

## Configuration

Create `~/.config/voltkeeper/config.yaml`:

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

Config is searched in order: `./voltkeeper.yaml`,
`~/.config/voltkeeper/config.yaml`, `/etc/voltkeeper/config.yaml`.

## Starting the daemon

```bash
voltkeeper daemon start          # runs in the foreground
```

## Daemon status and stop

```bash
voltkeeper daemon status         # list connected devices and SOC
voltkeeper daemon stop           # send stop signal
```

Both commands accept `--daemon-url` to target a daemon at a non-default URL.

## Querying the daemon from the CLI

The `status` and `write` commands can be routed through a running daemon
instead of connecting to BLE directly:

```bash
voltkeeper status --daemon localhost                        # all devices
voltkeeper status AA:BB:CC:DD:EE:FF --daemon localhost     # single device
voltkeeper write AA:BB:CC:DD:EE:FF ac_output on --daemon localhost
```

Pass a hostname or full URL; `localhost` expands to `http://localhost:8080`.

## Web UI

Open `http://localhost:8080` in a browser. Enter your API key when prompted.

## Running as a systemd service

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

Save as `/etc/systemd/system/voltkeeperd.service`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now voltkeeperd
```

## Network access control

Restrict which networks can reach the daemon by adding `allowed_networks`
to the config:

```yaml
server:
  api_key: "your-secret-key"
  allowed_networks: ["192.168.1.0/24", "127.0.0.0/8"]
```

Requests from addresses outside the listed CIDRs receive a 403 response.

# Daemon

For monitoring multiple devices simultaneously, a persistent Web UI, or
avoiding repeated BLE scans on every command, run `voltkeeperd` as a
background service.

## voltkeeperd vs. voltkeeper daemon

Two names, two roles:

- **`voltkeeperd`** — the daemon binary. Long-running process that polls
  devices over BLE and serves the REST API + Web UI. Use this in `ExecStart=`
  when writing custom unit files.

- **`voltkeeper daemon`** — the CLI management group. Subcommands that
  install, start, stop, and query the daemon. Runs as a normal command-line
  tool, not a background process.

## Installing as a systemd user service

The recommended way to run `voltkeeperd` is as a user-level systemd service.
No root access is required.

```bash
voltkeeper daemon install
```

This single command:

1. Generates a fresh API key and writes `~/.config/voltkeeper/config.yaml`
1. Writes a hardened unit file to `~/.config/systemd/user/voltkeeper.service`
1. Runs `systemctl --user daemon-reload`, `enable`, and `start`
1. Prints what it did and how to reach the daemon

If the service is already installed, the command prints the current status
and exits — it never overwrites an existing installation.

### LAN mode

To make the daemon reachable from other devices on your network and advertise
it via mDNS:

```bash
voltkeeper daemon install --lan
```

This sets `server.host: "0.0.0.0"` and `server.mdns: true` in the config.
The daemon will advertise itself as `voltkeeper-{hostname}._http._tcp.local.`
so other devices can discover it without knowing the IP address.

> **Security note**: `--lan` prints the API key in the install summary.
> Keep this key secret — anyone on your LAN who has it can control your
> devices.

### Uninstalling

```bash
voltkeeper daemon uninstall
```

Stops and disables the service, removes the unit file, and reloads systemd.
Config files and data are not removed.

## Stopping the daemon

```bash
voltkeeper daemon stop
```

If the systemd unit file is present, this runs `systemctl --user stop voltkeeper`.
Otherwise it sends a shutdown request to the daemon API.

## Daemon status

```bash
voltkeeper daemon status         # list connected devices and SOC
```

Accepts `--daemon-url` to target a daemon at a non-default URL.

## Configuration management

Use `voltkeeper config` to read and write daemon config without hand-editing YAML.
Changes to most settings are applied immediately via hot-reload; server host and
port changes require a daemon restart.

```bash
voltkeeper config show                              # display current config
voltkeeper config set scan.interval 120            # change scan interval
voltkeeper config set server.api_key new-secret    # rotate API key (restart required)
voltkeeper config add-device AA:BB:CC:DD:EE:FF --name "Living Room"
voltkeeper config remove-device AA:BB:CC:DD:EE:FF
```

### Settable keys

| Key              | Hot-reload | Description                          |
| ---------------- | ---------- | ------------------------------------ |
| `scan.interval`  | Yes        | Seconds between reconciliation scans |
| `scan.timeout`   | Yes        | BLE scan timeout in seconds          |
| `server.mdns`    | Yes        | Enable mDNS advertising              |
| `server.host`    | No         | Bind address (restart required)      |
| `server.port`    | No         | HTTP port (restart required)         |
| `server.api_key` | No         | API key (restart required)           |

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

Open `http://localhost:8080` in a browser (or the LAN address if using `--lan`).
Enter your API key when prompted.

## BLE exclusivity conflict

Bluetooth Low Energy allows only one active connection per device. If
`voltkeeperd` is polling a device and you run a direct BLE command against
the same device, both will fight over the connection.

Stop the daemon before using BLE commands directly:

```bash
voltkeeper daemon stop
voltkeeper status AA:BB:CC:DD:EE:FF   # direct BLE
voltkeeper daemon start               # or restore via systemctl
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

## TLS / HTTPS

The daemon does not terminate TLS directly. Place a reverse proxy (nginx,
Caddy, Traefik) in front of it and forward HTTPS traffic to `localhost:8080`.

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

The Web UI is a single-page interface served by the daemon itself at `/` (the
only unauthenticated route). It reads device state through the REST API and
subscribes to the WebSocket for live updates, so the page reflects changes as
they happen without refreshing. The API key is kept in the browser tab's
`sessionStorage` and is sent as an `Authorization: Bearer` header on REST calls
and as the `token` query parameter on the WebSocket connection.

## HTTP API Reference

The daemon exposes a small REST API plus a WebSocket stream, all served from
the daemon's HTTP port (default `8080`). Responses are JSON.

### Endpoint overview

| Method | Path                            | Auth | Description                                        |
| ------ | ------------------------------- | ---- | -------------------------------------------------- |
| GET    | `/`                             | No   | Web UI (single-page HTML interface)                |
| GET    | `/api/devices`                  | Yes  | List configured devices and their status           |
| GET    | `/api/device/{address}`         | Yes  | Latest state for one device                        |
| GET    | `/api/device/{address}/fields`  | Yes  | Writable fields and their allowed values           |
| POST   | `/api/device/{address}/command` | Yes  | Send a write command to a device                   |
| POST   | `/api/shutdown`                 | Yes  | Gracefully stop the daemon                         |
| POST   | `/api/reload`                   | Yes  | Reload config; hot-applies where possible          |
| GET    | `/ws`                           | Yes  | WebSocket: device status + real-time state updates |

`{address}` is a device BLE address in uppercase MAC form (e.g.
`AA:BB:CC:DD:EE:FF`).

### Authentication

Every endpoint except `/` requires the API key. It is the `server.api_key`
value from `~/.config/voltkeeper/config.yaml`, and the same key the Web UI
prompts for.

Two mechanisms are accepted:

- **`Authorization: Bearer <token>` header** — used by the REST clients
  (and by `voltkeeper status --daemon` / `voltkeeper write --daemon`):

  ```bash
  curl -H "Authorization: Bearer $VK_API_KEY" http://localhost:8080/api/devices
  ```

- **`?token=<token>` query parameter** — needed for the WebSocket, since
  browsers cannot set headers on a `WebSocket` handshake:

  ```
  ws://localhost:8080/ws?token=your-api-key
  ```

Requests without a valid key receive `401 {"error": "Unauthorized"}`.

### Rate limiting

The daemon enforces a limit of **60 requests per 60 seconds per client IP**.
Exceeding it returns `429 {"error": "Too Many Requests"}`. Rate limiting is
applied before authentication, and the `/` (Web UI) route is also subject to
it. Requests from disallowed networks never reach the auth layer — see
[Network access control](#network-access-control).

### List devices

`GET /api/devices`

Returns an array of every device in the daemon configuration, with a status
and a summary of the latest readings:

```json
[
  {
    "address": "AA:BB:CC:DD:EE:FF",
    "name": "Living Room",
    "type": "AC2A",
    "status": "online",
    "encrypted": true,
    "sn": "2305000123456",
    "summary": {"soc": 87, "voltage": 26.3},
    "last_heard": "2026-09-02T10:15:00+00:00"
  }
]
```

`status` is `online`, `missing`, or `new` (configured but not yet seen).
`last_heard` is an ISO-8601 timestamp of the most recent poll, or `null`.

### Get device state

`GET /api/device/{address}`

Returns the device's identity fields plus its latest parsed state. Device
registers are merged into the top-level object as `key: value` entries
(power, SOC, voltage, alarms, and so on), so the response shape is not fixed.

```json
{
  "address": "AA:BB:CC:DD:EE:FF",
  "name": "Living Room",
  "type": "AC2A",
  "status": "online",
  "_status": "online",
  "last_heard": "2026-09-02T10:15:00+00:00",
  "packTotalSoc": 87.0,
  "packTotalVoltage": 26.3
}
```

Unknown devices return `404 {"error": "Device not found"}`. The CLI equivalent
is `voltkeeper status AA:BB:CC:DD:EE:FF --daemon localhost`.

### Introspect writable fields

`GET /api/device/{address}/fields`

Returns the writable fields for the device together with what each accepts, so
clients can render a control without hardcoding field metadata:

```json
{
  "fields": [
    {"name": "ac_output", "type": "bool"},
    {"name": "charging_mode", "type": "enum", "values": ["standard", "silent", "turbo"]},
    {"name": "sys_low_power", "type": "int", "range": [0, 100]}
  ]
}
```

`type` is `bool` (values `on`/`off`), `enum` (see `values`), `int` (see
`range`), or `any`.

### Send a command

`POST /api/device/{address}/command`

Writes a field value. The request body is JSON:

```json
{"field": "ac_output", "value": "on"}
```

`value` accepts the same forms as the CLI (`on`/`off`, enum names, or numbers;
`"toggle"` flips a boolean). A successful write is queued to the device and
returns immediately:

```json
{"accepted": true}
```

Errors use HTTP status codes with a JSON error body:

| Status | Meaning                                                          |
| ------ | ---------------------------------------------------------------- |
| 400    | Invalid JSON body, unknown field, or invalid value for the field |
| 404    | Device not in configuration                                      |
| 503    | Device not currently online                                      |

The CLI equivalent is `voltkeeper write AA:BB:CC:DD:EE:FF ac_output on --daemon localhost`.

### Shut down the daemon

`POST /api/shutdown`

Gracefully stops the daemon. Returns `202 {"accepted": true}` and the process
exits once in-flight work completes.

### Reload configuration

`POST /api/reload`

Re-reads the config file. Scan interval, scan timeout, and the device list are
applied live; `server.host`, `server.port`, and `server.api_key` cannot be
applied to a running process.

A successful hot reload returns:

```json
{"reloaded": true, "restart_required": false}
```

If `server.host` or `server.port` changed, the daemon applies nothing and
returns `restart_required` with the reason:

```json
{"reloaded": false, "restart_required": true, "reason": "server.host changed"}
```

A changed `server.api_key` is not detected here: the endpoint reports
`{"reloaded": true, "restart_required": false}` while the running daemon keeps
serving with the old key. Restart the daemon after rotating the key.

### WebSocket stream

`GET /ws`

Upgrade endpoint for real-time updates. Authenticate with the `token` query
parameter (see [Authentication](#authentication)):

```
ws://localhost:8080/ws?token=your-api-key
```

On connect the daemon sends one message per device — a `device_status` message
with the current connection state — each followed by a cached `state_update`
carrying that device's latest readings, if any have been cached yet:

```json
{"type": "device_status", "device": "AA:BB:CC:DD:EE:FF", "status": "online", "name": "Living Room", "device_type": "AC2A"}
{"type": "state_update", "device": "AA:BB:CC:DD:EE:FF", "state": {"packTotalSoc": 87.0}}
```

After that, a `state_update` is pushed whenever a device reports fresh data,
so clients (like the Web UI) always see the current state without polling.
Every message is a JSON object with a `type` field (`device_status` or
`state_update`).

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

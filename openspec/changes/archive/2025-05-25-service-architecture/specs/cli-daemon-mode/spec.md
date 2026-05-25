## ADDED Requirements

### Requirement: Daemon subcommand group

The CLI SHALL expose a `voltkeeper daemon` Click group with `start`, `stop`, and `status` subcommands.

#### Scenario: daemon start subcommand

- **WHEN** user runs `voltkeeper daemon start`
- **THEN** the CLI starts the daemon process in the foreground (or prints instructions for systemd-based startup)

#### Scenario: daemon status subcommand

- **WHEN** user runs `voltkeeper daemon status`
- **THEN** the CLI checks whether the daemon is running and, if so, queries `/api/devices` to display a device summary table

#### Scenario: daemon stop subcommand

- **WHEN** user runs `voltkeeper daemon stop`
- **THEN** the CLI sends a shutdown signal to the running daemon

### Requirement: --daemon flag on status command

The `voltkeeper status` command SHALL accept an optional `--daemon <URL>` option. When provided, the command SHALL query the daemon's API instead of performing BLE operations. When omitted, the command SHALL use the existing standalone BLE flow.

#### Scenario: Status via daemon

- **WHEN** user runs `voltkeeper status --daemon http://localhost:8080` and the daemon is running with device AA:BB:CC:DD:EE:FF
- **THEN** the CLI issues `GET /api/devices` and displays a summary of all devices; user can select one for detailed view

#### Scenario: Status standalone (no flag)

- **WHEN** user runs `voltkeeper status` without `--daemon`
- **THEN** the CLI uses the existing standalone BLE scan+connect+read flow unchanged

#### Scenario: Status via daemon with explicit address

- **WHEN** user runs `voltkeeper status AA:BB:CC:DD:EE:FF --daemon http://localhost:8080`
- **THEN** the CLI issues `GET /api/device/AA:BB:CC:DD:EE:FF` and displays the full state

### Requirement: --daemon flag on write command

The `voltkeeper write` command SHALL accept an optional `--daemon <URL>` option. When provided, the command SHALL send the write command through the daemon's API instead of performing direct BLE operations.

#### Scenario: Write via daemon

- **WHEN** user runs `voltkeeper write AA:BB:CC:DD:EE:FF ac_output on --daemon http://localhost:8080` and the device is online
- **THEN** the CLI issues `POST /api/device/AA:BB:CC:DD:EE:FF/command` with `{"field": "ac_output", "value": true}` and reports the result

#### Scenario: Write standalone (no flag)

- **WHEN** user runs `voltkeeper write AA:BB:CC:DD:EE:FF ac_output on` without `--daemon`
- **THEN** the CLI uses the existing standalone BLE connect+write flow unchanged

### Requirement: Daemon URL resolution

The `--daemon` flag SHALL accept a URL with protocol and port. If the flag is passed without a value or with a bare host, the CLI SHALL default to `http://<host>:8080`.

#### Scenario: Full URL provided

- **WHEN** `--daemon http://192.168.1.10:9090` is passed
- **THEN** the CLI uses `http://192.168.1.10:9090` as the API base URL

#### Scenario: Bare hostname provided

- **WHEN** `--daemon localhost` is passed
- **THEN** the CLI resolves this to `http://localhost:8080`

### Requirement: API key handling for CLI daemon mode

When using `--daemon`, the CLI SHALL read the API key from the daemon's config file (discovered via the standard config search paths) and include it in the `Authorization` header of all API requests.

#### Scenario: Config file found with API key

- **WHEN** the CLI finds a config file at one of the standard paths that contains `server.api_key`
- **THEN** the API key is included in all daemon API requests

#### Scenario: No config file or no API key

- **WHEN** the CLI cannot find a config file or the found config has no `server.api_key`
- **THEN** the CLI warns the user that API key could not be discovered and attempts requests without authentication

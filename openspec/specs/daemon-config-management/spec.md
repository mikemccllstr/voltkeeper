## ADDED Requirements

### Requirement: Display current config
`voltkeeper config show` SHALL read the active config file and print its contents in a human-readable form. The API key SHALL be masked (showing only the first 4 characters followed by `...`). The command SHALL print the config file path it is reading from.

#### Scenario: Config file exists
- **WHEN** the user runs `voltkeeper config show`
- **THEN** the command prints the config file path and all config values with the API key masked

#### Scenario: No config file found
- **WHEN** the user runs `voltkeeper config show` and no config file exists
- **THEN** the command prints an error indicating where it searched and exits non-zero

### Requirement: Set scalar config values
`voltkeeper config set <key> <value>` SHALL update a single scalar config value using dot-notation keys (e.g., `server.port`, `scan.interval`). The command SHALL write the updated value back to the config file using `ruamel.yaml` to preserve existing comments and formatting. If a running daemon is reachable, the command SHALL attempt `POST /api/reload` after writing. The command SHALL report whether the change is hot-reloadable or requires a restart.

#### Scenario: Set a hot-reloadable value
- **WHEN** the user runs `voltkeeper config set scan.interval 120` and the daemon is reachable
- **THEN** the config file is updated, `POST /api/reload` is called, the daemon applies the change, and the CLI prints "Config reloaded successfully"

#### Scenario: Set a restart-required value
- **WHEN** the user runs `voltkeeper config set server.port 9090`
- **THEN** the config file is updated and the CLI prints "Restart required: server.port change takes effect after daemon restart"

#### Scenario: Invalid key
- **WHEN** the user runs `voltkeeper config set unknown.key value`
- **THEN** the command prints an error listing valid keys and exits non-zero

### Requirement: Add a device to config
`voltkeeper config add-device <address> [--name <name>]` SHALL append a new device entry to the `devices` list in the config file. The address SHALL be normalized to uppercase. If a device with that address already exists, the command SHALL print a message and make no change. If the daemon is reachable, the command SHALL call `POST /api/reload` after writing.

#### Scenario: Add new device
- **WHEN** the user runs `voltkeeper config add-device AA:BB:CC:DD:EE:FF --name "Garage AC2A"`
- **THEN** the device is appended to the config file's devices list and the daemon is reloaded if reachable

#### Scenario: Device already in config
- **WHEN** the user runs `voltkeeper config add-device` with an address already in the config
- **THEN** the command prints "Device AA:BB:CC:DD:EE:FF is already in config" and makes no change

### Requirement: Remove a device from config
`voltkeeper config remove-device <address>` SHALL remove the matching device entry from the `devices` list in the config file. If no device with that address exists, the command SHALL print a message and exit 0. If the daemon is reachable, the command SHALL call `POST /api/reload` after writing.

#### Scenario: Remove existing device
- **WHEN** the user runs `voltkeeper config remove-device AA:BB:CC:DD:EE:FF`
- **THEN** the device is removed from the config file and the daemon is reloaded if reachable

#### Scenario: Device not in config
- **WHEN** the user runs `voltkeeper config remove-device` with an address not in the config
- **THEN** the command prints a not-found message and exits 0

### Requirement: Config reload API endpoint
The daemon SHALL expose `POST /api/reload` (protected by API key) that re-reads the config file and applies any hot-reloadable changes. Hot-reloadable changes are: device list, scan interval, scan timeout. Restart-required changes are: server host, port. The response SHALL indicate which changes were applied and whether a restart is needed.

#### Scenario: Reload with hot-reloadable changes
- **WHEN** `POST /api/reload` is called after a change to `scan.interval`
- **THEN** the daemon applies the new value immediately and responds with `{"reloaded": true, "restart_required": false}`

#### Scenario: Reload with restart-required changes
- **WHEN** `POST /api/reload` is called after a change to `server.port`
- **THEN** the daemon responds with `{"reloaded": false, "restart_required": true, "reason": "server.port changed"}` and does not apply the new port

#### Scenario: Config file not found or invalid on reload
- **WHEN** `POST /api/reload` is called but the config file has a parse error
- **THEN** the daemon responds with 400 Bad Request, describes the error, and continues running with its current config

### Requirement: Config write preserves existing formatting
All config write operations (`config set`, `config add-device`, `config remove-device`) SHALL use `ruamel.yaml` for write-back to preserve user-added comments, blank lines, and formatting in the config file.

#### Scenario: Config file with comments is updated
- **WHEN** the user runs `voltkeeper config set scan.interval 120` on a config file containing YAML comments
- **THEN** the updated config file retains all existing comments and only the target value is changed

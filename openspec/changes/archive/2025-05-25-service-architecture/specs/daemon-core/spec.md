## ADDED Requirements

### Requirement: Config file loading

The daemon SHALL load its configuration from a YAML file searched in order: `./voltkeeper.yaml`, `~/.config/voltkeeper/config.yaml`, `/etc/voltkeeper/config.yaml`. The first file found wins.

#### Scenario: Config file found at default user path

- **WHEN** `~/.config/voltkeeper/config.yaml` exists and is valid YAML
- **THEN** the daemon loads and uses that configuration

#### Scenario: No config file found

- **WHEN** none of the search paths contain a config file
- **THEN** the daemon exits with a clear error message listing the paths it checked

#### Scenario: Config file with invalid YAML

- **WHEN** a config file is found but contains malformed YAML
- **THEN** the daemon exits with a parse error including the file path and line number

### Requirement: Device list in config

The config file SHALL support a `devices` list where each entry has `address` (MAC address) and optional `name` (friendly label).

#### Scenario: Config with two known devices

- **WHEN** config contains `devices: [{address: "AA:BB:CC:DD:EE:FF", name: "Living Room"}, {address: "11:22:33:44:55:66"}]`
- **THEN** both devices are registered with their addresses; the second device uses its address as the display name

### Requirement: Server settings in config

The config file SHALL support `server.host`, `server.port`, `server.api_key`, `server.allowed_networks`, and `server.interface` fields.

#### Scenario: Minimal server config

- **WHEN** config contains `server: {host: "0.0.0.0", port: 8080, api_key: "secret"}`
- **THEN** the HTTP server binds to all interfaces on port 8080 and requires the given API key

#### Scenario: Server config with network ACL

- **WHEN** `server.allowed_networks` contains `["192.168.1.0/24"]`
- **THEN** the daemon parses and stores the CIDR prefix for use by the ACL middleware

### Requirement: DeviceManager reconciliation

The DeviceManager SHALL reconcile the configured device list against periodic BLE scan results, classifying each device as one of: `online` (in config and in scan range), `missing` (in config but not in scan range), or `new` (in scan range but not in config).

#### Scenario: All configured devices found in scan

- **WHEN** config lists devices A and B, and BLE scan finds both A and B
- **THEN** both devices are classified as `online` and DeviceHandlers are created for both

#### Scenario: Configured device not in scan range

- **WHEN** config lists devices A and B, but BLE scan only finds A
- **THEN** device A is `online`, device B is `missing`, and B's missing status is surfaced in the API and logs

#### Scenario: Unrecognized device in scan range

- **WHEN** config lists device A, but BLE scan finds A and an unrecognized device C
- **THEN** device A is `online`, device C is classified as `new` and surfaced in the API and logs

### Requirement: DeviceManager scan scheduling

The DeviceManager SHALL perform reconciliation on startup and periodically at the interval specified in `scan.interval` (seconds).

#### Scenario: Periodic reconciliation

- **WHEN** `scan.interval` is set to 60
- **THEN** the DeviceManager runs a BLE scan and reconciliation every 60 seconds after the initial startup reconciliation

### Requirement: Multi-device EventBus

The EventBus SHALL route `ParserMessage` and `CommandMessage` instances from multiple DeviceHandler producers to all registered listeners, preserving the `device` field so listeners can distinguish sources.

#### Scenario: Two devices publishing to one listener

- **WHEN** DeviceHandler A publishes a ParserMessage and DeviceHandler B publishes a ParserMessage
- **THEN** a single parser-listener receives both messages and can distinguish them by `msg.device.address`

### Requirement: State store

The state store SHALL maintain the latest parsed state per device, keyed by device address, updated via an EventBus parser-listener.

#### Scenario: State updated on poll

- **WHEN** DeviceHandler for address "AA:BB:CC:DD:EE:FF" publishes a ParserMessage with `{"packTotalSoc": 85}`
- **THEN** the state store returns `{"packTotalSoc": 85}` when queried for "AA:BB:CC:DD:EE:FF"

#### Scenario: State absent for unknown device

- **WHEN** the state store is queried for an address with no published data
- **THEN** the query returns an empty dict or None

### Requirement: Daemon process lifecycle

The daemon SHALL start as a single asyncio process that initializes the EventBus, Config, DeviceManager, StateStore, HTTP server, and optional shutdown watchdog, and SHALL shut down cleanly on SIGTERM/SIGINT.

#### Scenario: Clean shutdown on SIGTERM

- **WHEN** the daemon receives SIGTERM
- **THEN** all BLE connections are disconnected, the HTTP server stops, and the process exits with code 0

#### Scenario: Restart on event loop crash

- **WHEN** an unhandled exception escapes the main event loop
- **THEN** the process exits with code 1 and logs the exception

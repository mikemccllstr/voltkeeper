## ADDED Requirements

### Requirement: Device list endpoint

The HTTP server SHALL expose `GET /api/devices` returning a JSON array of all known devices with their reconciliation status and latest state summary.

#### Scenario: Request device list

- **WHEN** an authenticated client sends `GET /api/devices`
- **THEN** the response is a 200 with a JSON array containing each device's address, name, type, status (online/missing/new), and summary fields (SOC, voltage, power)

#### Scenario: No devices configured or found

- **WHEN** an authenticated client sends `GET /api/devices` and no devices are configured or scanned
- **THEN** the response is a 200 with an empty JSON array

### Requirement: Single device state endpoint

The HTTP server SHALL expose `GET /api/device/<address>` returning the full latest parsed state for the specified device.

#### Scenario: Request state of online device

- **WHEN** an authenticated client sends `GET /api/device/AA:BB:CC:DD:EE:FF` and the device is online with known state
- **THEN** the response is a 200 with a JSON object containing all parsed fields and a `_status` field indicating "online"

#### Scenario: Request state of missing device

- **WHEN** an authenticated client sends `GET /api/device/11:22:33:44:55:66` and the device is configured but missing
- **THEN** the response is a 200 with a JSON object containing only the device metadata and `_status: "missing"`

#### Scenario: Request state of unknown device

- **WHEN** an authenticated client sends `GET /api/device/FF:EE:DD:CC:BB:AA` for an address not in config and not scanned
- **THEN** the response is a 404

### Requirement: Command endpoint

The HTTP server SHALL expose `POST /api/device/<address>/command` accepting a JSON body with field name and value, and SHALL route the command to the appropriate device via the EventBus.

#### Scenario: Write to online device

- **WHEN** an authenticated client sends `POST /api/device/AA:BB:CC:DD:EE:FF/command` with `{"field": "ac_output", "value": true}` and the device is online
- **THEN** the command is published as a CommandMessage on the EventBus and the response is 200 with `{"accepted": true}`

#### Scenario: Write to missing device

- **WHEN** an authenticated client sends a command to a configured but missing device
- **THEN** the response is 503 with an error message indicating the device is not connected

#### Scenario: Write to unknown device

- **WHEN** an authenticated client sends a command to an unknown address
- **THEN** the response is 404

### Requirement: WebSocket endpoint

The HTTP server SHALL expose a WebSocket at `/ws` that pushes JSON state updates for all devices on every poll cycle.

#### Scenario: Client receives state updates

- **WHEN** a WebSocket client connects and a DeviceHandler publishes new state for device A
- **THEN** the client receives a JSON message with `{"type": "state_update", "device": "<address>", "state": {...}}`

#### Scenario: Client receives device status change

- **WHEN** a device transitions from online to missing (BLE connection lost)
- **THEN** all connected WebSocket clients receive a JSON message with `{"type": "device_status", "device": "<address>", "status": "missing"}`

### Requirement: Authentication

All API requests SHALL require an `Authorization: Bearer <api-key>` header matching the `server.api_key` config value.

#### Scenario: Request with valid API key

- **WHEN** a client sends `GET /api/devices` with `Authorization: Bearer correct-key`
- **THEN** the request proceeds to the handler

#### Scenario: Request with invalid API key

- **WHEN** a client sends `GET /api/devices` with `Authorization: Bearer wrong-key`
- **THEN** the response is 401 with a JSON error body

#### Scenario: Request with no API key

- **WHEN** a client sends `GET /api/devices` without an Authorization header
- **THEN** the response is 401 with a JSON error body

### Requirement: Network ACL

Requests from client IPs not matching any CIDR prefix in `server.allowed_networks` SHALL be rejected with HTTP 403 before reaching the API layer.

#### Scenario: Request from allowed network

- **WHEN** `allowed_networks` is `["192.168.1.0/24"]` and a request arrives from `192.168.1.50`
- **THEN** the request passes the ACL check and reaches the API layer

#### Scenario: Request from disallowed network

- **WHEN** `allowed_networks` is `["192.168.1.0/24"]` and a request arrives from `10.0.0.5`
- **THEN** the response is 403 with a JSON error body before any API handler executes

### Requirement: Interface binding

When `server.interface` is set, the HTTP server SHALL bind only to the specified network interface's IP address.

#### Scenario: Bind to specific interface

- **WHEN** `server.interface` is `"eth0"` and eth0 has IP `192.168.1.10`
- **THEN** the HTTP server binds to `192.168.1.10` only

#### Scenario: Interface not specified

- **WHEN** `server.interface` is null or absent
- **THEN** the HTTP server binds to the address specified in `server.host` (default `0.0.0.0`)

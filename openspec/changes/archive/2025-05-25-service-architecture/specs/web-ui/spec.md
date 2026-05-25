## ADDED Requirements

### Requirement: Dashboard device overview

The web UI SHALL display a tile grid on the main page showing every known device with its name, type, online/missing/new status, battery SOC percentage, and current power flow.

#### Scenario: Two online devices displayed

- **WHEN** the daemon has two online devices with state data
- **THEN** the dashboard shows two tiles, each displaying the device name, SOC, and power values updated in real time

#### Scenario: Missing device displayed

- **WHEN** the daemon has one online device and one missing device
- **THEN** the dashboard shows the online device tile with live data and a visually distinct tile for the missing device indicating "Not in range"

#### Scenario: New device displayed

- **WHEN** the BLE scan discovers an unrecognized device
- **THEN** the dashboard shows a tile for the new device with an "Add to config" action button

### Requirement: Per-device detail view

Selecting a device tile SHALL navigate to a detail view showing all parsed fields grouped by category (battery, inverter, PV, grid, load), with writable fields rendered as interactive controls.

#### Scenario: Detail view with controls

- **WHEN** a user clicks an online device tile
- **THEN** the detail view shows all sensor values and renders toggleable controls for writable fields like AC output and charging mode

#### Scenario: Detail view for missing device

- **WHEN** a user clicks a missing device tile
- **THEN** the detail view shows the device metadata and a "Device not in range" message with no sensor data

### Requirement: Real-time updates via WebSocket

The dashboard SHALL maintain a WebSocket connection to `/ws` and update displayed values without page refresh when new state data arrives.

#### Scenario: SOC updates in real time

- **WHEN** the daemon publishes new SOC data for a device via WebSocket
- **THEN** the device tile's SOC display updates within 1 second without user interaction

#### Scenario: Device comes online

- **WHEN** a previously missing device appears in scan range and the daemon reconnects
- **THEN** the tile transitions from "missing" styling to "online" styling and begins showing live data

### Requirement: Control actions from UI

The web UI SHALL allow users to toggle outputs and change settings on online devices by sending commands through the API.

#### Scenario: Toggle AC output

- **WHEN** a user clicks the AC output toggle in a device detail view
- **THEN** a `POST /api/device/<addr>/command` request is sent, and the toggle reflects the result after the next poll cycle

#### Scenario: Command error handling

- **WHEN** a command request fails (e.g., device disconnects mid-request)
- **THEN** the UI displays an error message without breaking the dashboard

### Requirement: Web UI served from daemon

The web UI SHALL be a single static HTML file (with embedded CSS and JavaScript) served at the root path `/` from the same aiohttp server that serves the API.

#### Scenario: Browser loads dashboard

- **WHEN** a browser navigates to `http://<daemon-host>:8080/`
- **THEN** the dashboard HTML is served and the JavaScript begins polling the API and connecting the WebSocket

### Requirement: API key prompt

On first load, the web UI SHALL prompt the user for the API key if it is not already stored in the browser's localStorage.

#### Scenario: First visit prompts for key

- **WHEN** a browser navigates to the dashboard for the first time (no key in localStorage)
- **THEN** a prompt dialog asks for the API key before any API calls are made

#### Scenario: Returning visit uses stored key

- **WHEN** a browser navigates to the dashboard and a key exists in localStorage
- **THEN** the key is used for all API calls without prompting

## 1. Dependencies and scaffolding

- [x] 1.1 Add `aiohttp` to pyproject.toml dependencies and run `uv sync`
- [x] 1.2 Create `src/voltkeeper/config.py` — config file search, YAML load/validate, typed config model
- [x] 1.3 Create `src/voltkeeper/state_store.py` — in-memory dict with EventBus listener, thread-safe reads

## 2. Config file and state store

- [x] 2.1 Implement config file search across well-known paths, YAML parsing with clear error messages
- [x] 2.2 Implement config schema validation: required fields (server.host, server.port, server.api_key), optional sections (scan, shutdown_watchdog), device list with address
- [x] 2.3 Write unit tests for config loading: valid config, missing file, invalid YAML, missing required fields, empty device list
- [x] 2.4 Implement StateStore class: dict keyed by device address, `get(address)`, `get_all()`, EventBus parser-listener registration
- [x] 2.5 Write unit tests for StateStore: update on parser message, query for known/unknown address, concurrent read safety

## 3. DeviceManager

- [x] 3.1 Implement DeviceManager class: accepts Config, EventBus, scan settings; owns reconciliation logic
- [x] 3.2 Implement reconciliation: compare config device list against BLE ScanResult list, classify as online/missing/new
- [x] 3.3 Implement DeviceHandler lifecycle: create handler per online device, run in asyncio tasks, recreate on reconnect
- [x] 3.4 Implement scan scheduling: initial reconciliation on startup, periodic scans per `scan.interval`
- [x] 3.5 Surface reconciliation state via API-facing data structure (all devices with status, metadata)
- [x] 3.6 Write unit tests: two online devices, one missing, new device in scan, device transitions online→missing→online

## 4. Daemon process

- [x] 4.1 Implement `src/voltkeeper/daemon.py` — main entry point: load config, create EventBus, StateStore, DeviceManager, start HTTP server
- [x] 4.2 Implement graceful shutdown on SIGTERM/SIGINT: disconnect all BLE clients, stop HTTP server, cancel tasks
- [x] 4.3 Implement main loop: run all components in single asyncio event loop
- [x] 4.4 Write integration test: daemon starts, config loads, devices reconcile (mock BLE scan)

## 5. HTTP API — server and middleware

- [x] 5.1 Implement `src/voltkeeper/api.py` — aiohttp Application with route registration, startup/shutdown hooks
- [x] 5.2 Implement auth middleware: extract `Authorization: Bearer <key>` header, compare against config `server.api_key`, return 401 on mismatch
- [x] 5.3 Implement ACL middleware: parse CIDR prefixes from config, check client IP, return 403 for non-matching IPs
- [x] 5.4 Implement interface binding: resolve `server.interface` to IP, bind server to that address
- [x] 5.5 Write unit tests for middleware: valid/invalid/missing API key, allowed/disallowed IP ranges

## 6. HTTP API — REST endpoints

- [x] 6.1 Implement `GET /api/devices` — return JSON array of all devices with status, metadata, state summary
- [x] 6.2 Implement `GET /api/device/{address}` — return full latest state for device, or 404 for unknown
- [x] 6.3 Implement `POST /api/device/{address}/command` — accept `{"field": "...", "value": ...}`, publish CommandMessage to EventBus, return accepted/error
- [x] 6.4 Implement error handling: 400 for malformed JSON, 404 for unknown device, 503 for offline device
- [x] 6.5 Write unit tests: mock EventBus + StateStore, test each endpoint with valid/invalid inputs

## 7. HTTP API — WebSocket

- [x] 7.1 Implement `/ws` WebSocket endpoint: accept connection, register EventBus listener, push state updates and device status changes as JSON
- [x] 7.2 Handle WebSocket lifecycle: send initial state on connect, push deltas on poll, handle disconnect cleanly
- [x] 7.3 Write unit test: mock EventBus, connect WebSocket client, publish message, assert client receives correct JSON

## 8. Web UI

- [x] 8.1 Create single static HTML file with embedded CSS and JavaScript — served at `/` from the aiohttp server
- [x] 8.2 Implement dashboard tile grid: fetch `/api/devices`, render device cards with name, type, status, SOC, power
- [x] 8.3 Implement real-time updates: WebSocket connection to `/ws`, update tile values on state messages, update status on device_status messages
- [x] 8.4 Implement device detail view: click tile → show all fields grouped by category, writable fields as controls (toggles, selects)
- [x] 8.5 Implement control actions: toggle/select sends POST to `/api/device/{addr}/command`, updates UI on next poll
- [x] 8.6 Implement API key prompt: check localStorage, prompt on first visit, store for subsequent visits
- [x] 8.7 Implement "new device" tile: show unrecognized device with "Add to config" button (instructional for now — manual config edit)
- [x] 8.8 Implement "missing device" tile: visually distinct, shows "Not in range" message
- [x] 8.9 Implement responsive layout: tile grid adapts to viewport width
- [x] 8.10 Write visual regression test plan (manual): verify dashboard renders correctly with 0, 1, 3+ devices

## 9. CLI daemon subcommands

- [x] 9.1 Add `voltkeeper daemon` Click group with `start`, `stop`, `status` subcommands
- [x] 9.2 Implement `daemon start`: print instructions for starting the daemon (foreground or systemd)
- [x] 9.3 Implement `daemon status`: check if daemon is running, query `/api/devices` via HTTP, display device summary table
- [x] 9.4 Implement `daemon stop`: send shutdown signal (POST to shutdown endpoint, or SIGTERM if same host)
- [x] 9.5 Write integration test: daemon status subcommand with mocked HTTP response

## 10. CLI --daemon mode for status and write

- [x] 10.1 Add `--daemon` Click option to `voltkeeper status` command: when set, make HTTP requests instead of BLE operations
- [x] 10.2 Implement API key discovery: read config file from standard paths, extract `server.api_key`
- [x] 10.3 Implement URL resolution: full URL or bare hostname → default to port 8080
- [x] 10.4 Implement status via daemon: query `/api/devices`, display device list, support address argument for detail view
- [x] 10.5 Add `--daemon` Click option to `voltkeeper write` command: when set, POST command to daemon API
- [x] 10.6 Preserve standalone CLI paths: no behavior change when `--daemon` is omitted
- [x] 10.7 Write unit tests: CLI status/write with --daemon flag, mock HTTP responses

## 11. Shutdown watchdog

- [ ] 11.1 Implement shutdown watchdog as EventBus listener in the daemon: monitor configured device SOC via StateStore
- [ ] 11.2 Implement latched countdown: start when SOC drops below threshold, continue even if SOC recovers
- [ ] 11.3 Implement shutdown execution: `sudo shutdown -h now` on countdown expiry, with logging
- [ ] 11.4 Write unit tests: SOC drop triggers countdown, SOC recovery does not cancel, countdown expiry triggers shutdown (mock subprocess)

## 12. Integration and hardening

- [x] 12.1 Test multiple DeviceHandlers in single event loop against real hardware (two devices simultaneously)
- [x] 12.2 Test HTTP API against running daemon: curl endpoints, verify responses
- [x] 12.3 Test Web UI against running daemon: browser load, real-time updates, control actions
- [x] 12.4 Test CLI --daemon mode against running daemon: status, write
- [x] 12.5 Run full test suite: `mise run check` (lint + typecheck + test) — all existing tests still pass
- [x] 12.6 Verify standalone CLI commands unchanged: `voltkeeper scan`, `status`, `write`, `probe` all work without daemon
- [x] 12.7 Document daemon setup in README.md: config file format, systemd unit example, quickstart

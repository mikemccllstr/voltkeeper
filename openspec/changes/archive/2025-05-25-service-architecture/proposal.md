## Why

Voltkeeper currently operates in two isolated modes: a one-shot CLI that connects to a single device per invocation, and an MQTT-publish daemon tied to one device. As users acquire multiple Bluetti devices, this breaks down — there is no way to monitor or control multiple devices from a single process, no web dashboard, and every CLI command pays a BLE round-trip. A long-running service that stays connected to all devices and serves multiple consumers (CLI, web UI, future HA integration) is the foundation for every feature on the roadmap.

## What Changes

- **New daemon (`voltkeeperd`)** — persistent asyncio process that discovers, connects to, and polls multiple Bluetti devices simultaneously.
- **DeviceManager** — reconciles a user-editable config file (expected devices) against periodic BLE scans (actual devices in range), surfacing online, missing, and unrecognized devices for user accommodation.
- **In-memory state store** — latest parsed state for every connected device, populated by EventBus listeners so API queries return instantly without BLE round-trips.
- **HTTP REST API + WebSocket** — serves device state and accepts commands. Secured by API-key auth, network-range allow-listing, and interface binding.
- **Web UI** — static HTML/CSS/JS dashboard served by the daemon, providing multi-device monitoring and control over the LAN.
- **CLI daemon integration** — new `voltkeeper daemon` subcommand for lifecycle management, plus a `--daemon` flag on `status` and `write` that routes those commands through the HTTP API instead of direct BLE. Standalone CLI mode is fully preserved.
- **Shutdown watchdog folded into daemon** — minimal single-host shutdown when the powering battery's SOC drops below threshold.
- Existing MQTT client code is preserved but not modified or integrated into the daemon in this change.

## Capabilities

### New Capabilities

- `daemon-core`: The voltkeeperd process lifecycle, YAML config file format, DeviceManager (config+scan reconciliation), in-memory state store, multi-device EventBus routing.
- `http-api`: REST endpoints for device listing, state queries, and commands; WebSocket for real-time state push; API-key authentication; network-range allow-listing; server interface binding.
- `web-ui`: Static HTML/CSS/JS dashboard served from the daemon; multi-device overview tile grid; per-device detail view with monitoring and controls; device config management (add/remove known devices).
- `cli-daemon-mode`: `voltkeeper daemon [start|stop|status]` subcommand for lifecycle management; `--daemon` flag on `status` and `write` commands routing through the HTTP API; standalone CLI paths preserved unchanged.
- `shutdown-watchdog`: Minimal shutdown trigger integrated into the daemon event loop; watches SOC of a designated device via the state store; executes `sudo shutdown -h now` after a latched countdown.

### Modified Capabilities

None. Existing standalone CLI, BLE transport, device models, MQTT client, probe/validate/annotate tools are all preserved with no spec-level changes.

## Impact

- **New modules**: `src/voltkeeper/daemon.py`, `src/voltkeeper/api.py`, `src/voltkeeper/web.py`, `src/voltkeeper/config.py`, `src/voltkeeper/state_store.py`
- **Modified modules**: `src/voltkeeper/cli.py` (add `daemon` group, `--daemon` flag to `status`/`write`), `src/voltkeeper/bus.py` (multi-device routing), `src/voltkeeper/device_handler.py` (minor adjustments for multi-instance coordination)
- **New dependency**: aiohttp (async HTTP server + WebSocket), PyYAML (already present)
- **Untouched**: `bluetooth/`, `core/`, `mqtt_client.py`, `shutdown_watch.py`, `load_test.py`, `probe.py`, `validate.py`, `annotate.py`
- **Config file**: new YAML file at a well-known path (e.g., `~/.config/voltkeeper/config.yaml` or `/etc/voltkeeper/config.yaml`) for device list and server settings

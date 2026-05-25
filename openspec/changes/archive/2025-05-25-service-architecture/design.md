## Context

Voltkeeper has a layered architecture (BLE transport → Modbus → register parsing → device model → application) that works well. The current application layer has two modes: one-shot CLI commands and a single-device MQTT-publish daemon. Neither mode supports multiple simultaneous devices, and there is no persistent state, no API surface, and no web UI.

This design adds a new application layer — a long-running daemon process that orchestrates multiple BLE connections and serves a REST/WebSocket API. The existing layers (bluetooth/, core/devices/, core/commands/, core/struct/) are not modified. The standalone CLI is preserved as the first-touch onboarding experience.

## Goals / Non-Goals

**Goals:**
- A single asyncio process (`voltkeeperd`) that maintains persistent BLE connections to multiple devices
- User-editable YAML config for device list and server settings
- DeviceManager that reconciles configured devices against BLE scan results, surfacing online/missing/new states
- In-memory state store with the latest parsed data per device, updated via EventBus
- HTTP REST API and WebSocket serving device state and accepting commands
- API-key authentication and network-range allow-listing
- Web UI dashboard (static HTML/JS, served by daemon) for multi-device monitoring and control
- CLI subcommand (`voltkeeper daemon`) for lifecycle management
- `--daemon` flag on `status`/`write` CLI commands routing through API
- Minimal shutdown watchdog folded into daemon

**Non-Goals:**
- Modifying MQTT client or HA integration (preserved as-is)
- Modifying standalone CLI paths, BLE transport, device models, or discovery toolkit
- Persistent/historical data storage (state is ephemeral, in-memory only)
- Remote access or TLS (LAN-only, TLS adds complexity without corresponding risk)
- Multi-user auth (single API key shared by all consumers)
- Windows/macOS daemon support (Linux-only for daemon, systemd integration)

## Decisions

### 1. HTTP framework: aiohttp

**Decision:** Use aiohttp for the HTTP server, REST API, and WebSocket support.

**Rationale:** aiohttp is a single async-native dependency that provides HTTP serving, routing, middleware (for auth/ACL), and native WebSocket support. It integrates cleanly with the existing asyncio event loop — the HTTP server, DeviceHandlers, EventBus, and BLE connections all run in the same loop without threading. Alternatives considered:

- **FastAPI/Starlette** — richer typing, auto-docs, but adds uvicorn orchestration overhead and pydantic/lib dependency tree. Overkill for a small embedded API.
- **Flask + gunicorn** — synchronous framework requiring threads/processes to coexist with asyncio BLE operations. Adds complexity for no benefit.

### 2. Config file: YAML at well-known paths

**Decision:** YAML config file searched in order: `./voltkeeper.yaml` (cwd), `~/.config/voltkeeper/config.yaml`, `/etc/voltkeeper/config.yaml`. First found wins.

**Rationale:** YAML is already a project dependency (used by probe/annotate profiles). Well-known search paths follow XDG conventions and allow per-user, system-wide, and project-local overrides. No environment-variable config; a single file is simpler to document and debug.

### 3. DeviceManager reconciliation model

**Decision:** Three-state reconciliation with user notifications via logs and API.

```
              Config file              BLE scan result
              (expected)               (actual in range)
                  │                         │
                  └──────────┬──────────────┘
                             ▼
                    ┌────────────────┐
                    │  Reconciliation │
                    └───┬────────┬───┘
                        │        │
           ┌────────────┼────────┼────────────┐
           ▼            ▼        ▼            │
     "online"      "missing"  "new"           │
     connect +     log + API  log + API       │
     poll          surface     surface        │
                                             │
          User accommodates via config edit   │
          (add new device, remove missing,    │
           or ignore — daemon tolerates all)  │
```

Reconciliation runs on startup and periodically (configurable `scan.interval`). Devices in `online` state get a `DeviceHandler` instance. Devices in `missing` or `new` state are surfaced through the API (so the web UI can show them) and logs, but no BLE connection is attempted until the user adds them to config.

**Rationale:** Auto-connecting to every scanned device would be surprising and could connect to devices the user doesn't intend to manage. A config-first approach with graceful handling of missing/unexpected devices gives the user control without papering over real issues.

### 4. State store: in-memory dict, EventBus-driven

**Decision:** A plain `dict[str, dict]` mapping device address → latest parsed state. An EventBus parser-listener updates it on every poll cycle.

```
DeviceHandler → EventBus.put(ParserMessage) → StateStore listener updates dict
                                                 │
                                    ┌────────────┼────────────┐
                                    ▼            ▼            ▼
                               REST API     WebSocket      Shutdown
                               (reads dict) (reads dict    Watchdog
                                            then pushes)   (reads dict)
```

**Rationale:** No database needed. State is inherently ephemeral — each poll cycle replaces the previous snapshot. The last-known state is what every consumer wants. Adding a database would introduce schema management, migrations, and query complexity for no value.

### 5. API authentication: header-based API key

**Decision:** Require an `Authorization: Bearer <api-key>` header on all API requests. The key is configured in `config.yaml`. Requests without matching key get HTTP 401.

**Rationale:** Simple to implement, simple to configure. LAN-only HTTP means token-based auth is sufficient — no JWT expiry, no OAuth, no session management. A single key shared by CLI, web UI, and any other local consumer.

### 6. Network ACL: prefix-based allowlisting

**Decision:** The `server.allowed_networks` config accepts CIDR prefixes. A middleware checks the client IP against the list. Requests from non-allowed IPs get HTTP 403. Matching happens before auth — an unlisted IP never reaches the API layer.

**Rationale:** Network-layer filtering adds defense in depth. On a multi-homed machine, binding to a specific interface is not enough to prevent access from other hosts on the same LAN segment. CIDR matching covers the common case of "allow my home LAN but nothing else."

### 7. Web UI: single-page static app

**Decision:** A single `index.html` with embedded CSS and JavaScript, served at `/`. Loads device list from `/api/devices` and subscribes to `/ws` for real-time updates. No build step, no framework, no npm.

**Rationale:** The web UI scope is small — a dashboard with device card tiles, a detail view, and a config management panel. A server-side template engine or a JS framework adds toolchain complexity disproportionate to the UI's size. Vanilla JS with the Fetch API and WebSocket is sufficient and maintainable.

### 8. CLI daemon mode: flag-based routing

**Decision:** Add `--daemon <URL>` as an option on `status` and `write` commands. When present, the command makes HTTP requests to the daemon API instead of performing BLE operations. A new `voltkeeper daemon` Click group provides `start`, `stop`, and `status` subcommands.

**Rationale:** A flag keeps the existing command signatures intact. Users who don't run a daemon never see the flag. The daemon group follows the existing CLI pattern of subcommand groups.

### 9. Shutdown watchdog: EventBus listener

**Decision:** When `shutdown_watchdog.enabled` is true, the daemon registers an EventBus parser-listener that watches the configured device's SOC. When SOC drops below the threshold, a latched countdown begins (cannot be cancelled by SOC recovery). On expiry, runs `sudo shutdown -h now`.

**Rationale:** Folding it into the daemon eliminates a separate systemd service, a separate MQTT subscription, and the latency of the MQTT round-trip. The daemon already has the data. The latching behavior from the existing `shutdown_watch.py` implementation is preserved.

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                     voltkeeperd (single process)                  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                     DeviceManager                             │ │
│  │  ┌──────────┐    ┌───────────┐    ┌──────────────────────┐   │ │
│  │  │  Config   │    │  Periodic │    │    Reconciliation     │   │ │
│  │  │  (YAML)   │───▶│  BLE Scan │───▶│  online│missing│new  │   │ │
│  │  └──────────┘    └───────────┘    └──────────┬───────────┘   │ │
│  └──────────────────────────────────────────────┼───────────────┘ │
│                                                  │ online          │
│         ┌────────────────────────────────────────┘                │
│         ▼                                                         │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  DeviceHandler pool                                       │    │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐          │    │
│  │  │ Device A   │  │ Device B   │  │ Device C   │  ...     │    │
│  │  │ BLE→Modbus │  │ BLE→Modbus │  │ BLE→Modbus │          │    │
│  │  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘          │    │
│  └────────┼───────────────┼───────────────┼─────────────────┘    │
│           │               │               │                       │
│           └───────┬───────┴───────┬───────┘                      │
│                   ▼               ▼                               │
│           ┌──────────────────────────────┐                       │
│           │         EventBus             │                       │
│           └──────────────┬───────────────┘                       │
│                          │                                        │
│     ┌────────────────────┼────────────────────┐                  │
│     ▼                    ▼                     ▼                  │
│  ┌──────────┐   ┌───────────────┐   ┌──────────────────┐        │
│  │  State   │   │   aiohttp     │   │   Shutdown       │        │
│  │  Store   │   │   Server      │   │   Watchdog       │        │
│  │  (dict)  │   │               │   │   (opt)          │        │
│  └────┬─────┘   └───────┬───────┘   └──────────────────┘        │
│       │                 │                                         │
└───────┼─────────────────┼─────────────────────────────────────────┘
        │                 │
   ┌────▼────┐     ┌──────▼──────┐
   │  MQTT   │     │  :8080      │
   │  Client │     │  REST + WS  │
   │(existing│     └──────┬──────┘
   │ code)   │            │
   └─────────┘    ┌───────┼───────┐
                  │       │       │
             ┌────▼──┐ ┌──▼───┐ ┌─▼──────┐
             │ Web UI│ │ CLI  │ │ Future │
             │(browser│ │(--da│ │ HA     │
             │)      │ │emon) │ │ integ. │
             └───────┘ └─────┘ └────────┘
```

## Risks / Trade-offs

- **[Risk] BLE connection limits** — Linux BlueZ has practical limits on concurrent BLE connections (typically 5-20 depending on adapter). With many devices, connection starvation may occur. → **Mitigation**: Document the limit. The reconciliation model handles it gracefully — extra devices report as "online" but may face connection contention. Future: support multiple Bluetooth adapters.

- **[Risk] Single process, no crash isolation** — If one DeviceHandler's BLE failure crashes the event loop, all devices lose connectivity. → **Mitigation**: DeviceHandler already catches `BleakError` and `BadConnectionError` and reconnects. The asyncio event loop is robust. Wrap the main loop in a restart-on-failure guard. Systemd `Restart=always` provides process-level recovery.

- **[Risk] Config file editing complexity** — Users must edit YAML to add/remove devices. YAML syntax errors break the daemon. → **Mitigation**: Validate config on load with clear error messages. The web UI will eventually provide config management without YAML editing, but the config file remains the authoritative source.

- **[Risk] Web UI static assets** — A single HTML file with embedded CSS/JS works for a simple dashboard but becomes unwieldy as the UI grows. → **Mitigation**: Accept as a trade-off for Phase 1. If the UI outgrows the single-file approach, extracting CSS/JS to separate files or adopting a lightweight framework is straightforward without architectural change.

- **[Risk] aiohttp dependency** — Adds a new dependency to the project. → **Mitigation**: aiohttp is mature, well-maintained, and used by many async Python projects. It is the natural choice for an already-asyncio codebase.

## Open Questions

None — all key decisions resolved through exploration and user confirmation.

## Context

The voltkeeper daemon (`voltkeeperd`) is a long-running aiohttp process that polls Bluetti devices over BLE and serves a REST API, WebSocket, and Web UI. Today it has no install tooling — users must hand-write systemd unit files with no security hardening, edit YAML config manually, and the `daemon stop` CLI command is a no-op. The `daemon.py` entry point and `voltkeeper daemon start` subcommand are inconsistently documented, causing confusion about how to run the daemon.

The target model is a home LAN appliance: always-on, browseable from a phone, discoverable without knowing the host's IP address. The daemon should be as self-installing as a consumer IoT device while being transparent about what it does.

## Goals / Non-Goals

**Goals:**
- `voltkeeper daemon install` installs a hardened user-level systemd service in one command
- Install is idempotent: safe to run again, shows current state if already installed
- `voltkeeper daemon stop` actually stops the daemon
- `voltkeeper config` CLI reads and writes config without hand-editing YAML
- Daemon reloads config without a full restart when possible
- With `--lan`, daemon binds on all interfaces and advertises via mDNS
- Docs clearly distinguish `voltkeeperd` (daemon binary / ExecStart) from `voltkeeper daemon` (CLI management)

**Non-Goals:**
- TLS termination (document reverse proxy instead)
- `load-test` via daemon API
- Web UI config editing (CLI is sufficient for now)
- System-level (`/etc/systemd/system/`) service management (document as advanced path only)
- Multi-user or multi-daemon orchestration

## Decisions

### 1. User systemd service, not system service

**Decision**: Default to `~/.config/systemd/user/voltkeeper.service` (`WantedBy=default.target`), no `sudo` required.

**Rationale**: The daemon needs BLE access but not root. User services run as the logged-in user, accessing the user's config at `~/.config/voltkeeper/`, and require no privilege escalation to install. System service is documented as the advanced path for headless/server deployments.

**Alternative considered**: Always install as system service. Rejected — requires sudo, encourages running as root, complicates config file location.

### 2. ruamel.yaml for config write-back

**Decision**: Use `ruamel.yaml` (new dependency) for reading and writing config files; retain `pyyaml` for backward compatibility if needed.

**Rationale**: `pyyaml` strips comments on write. Users who hand-edit their config (adding comments, organizing sections) should not have those comments destroyed by `voltkeeper config set`. `ruamel.yaml` is a mature, widely-used library that round-trips comments correctly.

**Alternative considered**: Accept comment loss with `pyyaml`. Rejected — this silently degrades user-edited configs and feels hostile.

### 3. POST /api/shutdown and POST /api/reload, not SIGHUP

**Decision**: Add two authenticated API endpoints: `POST /api/shutdown` for graceful stop, `POST /api/reload` for config reload. `daemon stop` prefers `systemctl --user stop` when the unit file exists, otherwise calls `/api/shutdown`.

**Rationale**: SIGHUP is process-oriented and awkward to target when the daemon might be running under systemd (finding the PID is fragile). HTTP endpoints are consistent with the existing API design, work regardless of how the daemon was started, and can be authenticated with the existing API key.

**Reload semantics**: Hot-reloadable changes (device list, scan intervals) are applied immediately. Restart-required changes (host, port) are detected and reported — the daemon tells the CLI "restart required for these settings."

**Alternative considered**: SIGHUP. Rejected — PID file management adds complexity and SIGHUP is awkward to send via the CLI from a different process without a PID file.

### 4. Loopback by default, LAN opt-in via --lan

**Decision**: `daemon install` defaults to `server.host: "127.0.0.1"`. `daemon install --lan` sets `server.host: "0.0.0.0"` and enables mDNS. No prompt; the flag is the user's explicit choice.

**Rationale**: Principle of least surprise for security — binding to a LAN interface without the user asking is unexpected and potentially exposes the API key to other devices. The `--lan` flag makes the intent explicit and is documented with a security note.

### 5. mDNS naming: voltkeeper-{hostname}

**Decision**: Advertise as `voltkeeper-{hostname}._http._tcp.local.` (e.g., `voltkeeper-homelab._http._tcp.local.`).

**Rationale**: Plain `voltkeeper.local` would collide on networks with multiple machines running voltkeeperd. Hostname-qualified names are always unique on a LAN.

**Library**: `python-zeroconf` — pure Python, widely used, supports both advertising and browsing.

**mDNS activation**: Only when `server.host != "127.0.0.1"` (i.e., daemon is LAN-accessible). Advertising a loopback address via mDNS is nonsensical.

### 6. Hardened unit file from day 1

The generated unit file includes the full set of systemd security directives. This is not something to add incrementally — the hardening either applies or it doesn't.

Key directives:
- `PrivateTmp=true`, `NoNewPrivileges=true`, `ProtectSystem=strict`
- `ProtectHome=read-only` + `ReadWritePaths=%h/.config/voltkeeper`
- `RestrictAddressFamilies=AF_INET AF_INET6 AF_BLUETOOTH AF_UNIX`
- `SystemCallFilter=@system-service`, `SystemCallArchitectures=native`
- `AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW`, `CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_RAW`
- `MemoryMax=256M`, `TasksMax=64`
- `WantedBy=default.target` (correct for user services)

### 7. Idempotent install UX: inform, don't overwrite

**Decision**: If the unit file already exists, `daemon install` prints current state (status, config path, URL, log command) and exits 0. It does NOT overwrite.

**Rationale**: Silent overwrite could destroy user customizations. Prompt-before-overwrite adds friction. Idempotent inform is safe and useful.

## Risks / Trade-offs

- **ruamel.yaml dependency**: Adds ~500KB to the install. Risk is low — it's a stable, well-maintained library. Mitigation: add to `[project.dependencies]` in `pyproject.toml`.

- **BLE + daemon conflict**: If the daemon is polling a device and the user runs a direct BLE command against the same device, both will fight over the connection. The `daemon stop` command is the intended mitigation. This conflict is inherent to BLE's single-connection model and should be documented prominently.

- **User lingered services**: User systemd services only run when the user is logged in, unless the user has enabled lingering (`loginctl enable-linger`). For a headless server, the system-level service is the right path. This is an acceptable limitation for the target use case (personal workstation / always-logged-in user).

- **mDNS reliability**: mDNS can fail to propagate on some managed networks or behind certain routers. This is an inherent limitation of mDNS, not voltkeeper-specific. Document the direct URL as the fallback.

## Migration Plan

This change is purely additive. No existing behavior changes. The only migration concern:

- Users who have hand-written systemd unit files: `daemon install` will detect the existing file and inform them rather than overwriting. They can update their unit file manually or uninstall and reinstall.
- The `pyyaml` import in `config.py` is retained for reading. `ruamel.yaml` is added for writes. No config file format changes.

## Open Questions

None — all decisions were resolved during design exploration.

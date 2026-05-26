## Why

The voltkeeper daemon has no first-class install story: users must hand-write systemd unit files, edit YAML config by hand, and the `daemon stop` command does nothing. For a tool that is meant to act like an always-on LAN appliance (browseable from a phone, discoverable on the network), the current experience is too rough and the daemon's security posture is uncontrolled.

## What Changes

- **`voltkeeper daemon install`** — installs the daemon as a hardened user-level systemd service, idempotently; `--lan` flag enables LAN binding and mDNS discovery
- **`voltkeeper daemon uninstall`** — removes the service, with confirmation
- **`voltkeeper daemon stop`** — actually stops the running daemon (via `systemctl --user stop` or `POST /api/shutdown`)
- **`voltkeeper config show/set/add-device/remove-device`** — CLI for reading and writing the config file without hand-editing YAML
- **`POST /api/reload`** — daemon endpoint to hot-reload config after CLI changes
- **`POST /api/shutdown`** — daemon endpoint for clean remote shutdown
- **mDNS advertising** — when `--lan` is used, the daemon advertises itself as `voltkeeper-{hostname}._http._tcp.local.` via `python-zeroconf`
- **Docs cleanup** — clarify the `voltkeeperd` binary vs. `voltkeeper daemon` distinction; rewrite the daemon user guide around the install-first workflow

## Capabilities

### New Capabilities

- `daemon-lifecycle`: Install, uninstall, and stop the daemon as a user-level systemd service, including hardened unit file generation and idempotent install behavior
- `daemon-config-management`: CLI commands to read and write daemon configuration, with automatic daemon reload on change; daemon exposes `/api/reload` and `/api/shutdown`
- `daemon-lan-discovery`: Optional LAN binding (`--lan` install flag) with mDNS advertising so the daemon is reachable from other devices without knowing its IP

### Modified Capabilities

<!-- none -->

## Impact

- **`src/voltkeeper/cli.py`** — new `daemon install/uninstall/stop`, new `config` command group
- **`src/voltkeeper/daemon.py`** — SIGTERM/shutdown endpoint, config reload signal handling
- **`src/voltkeeper/api.py`** — add `POST /api/reload`, `POST /api/shutdown`
- **`src/voltkeeper/config.py`** — write-back support via `ruamel.yaml`; new `mdns` config field
- **`docs/source/user-guide/daemon.md`** — rewritten around install-first workflow
- **`docs/source/user-guide/systemd.md`** — updated; daemon install section added
- **New dependency**: `python-zeroconf` (mDNS); `ruamel.yaml` (config write-back, replaces comment-lossy pyyaml for writes)

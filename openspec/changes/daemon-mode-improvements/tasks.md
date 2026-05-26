## 1. Dependencies and Config Foundation

- [x] 1.1 Add `ruamel.yaml` and `python-zeroconf` to `pyproject.toml` dependencies
- [x] 1.2 Add `mdns: bool = False` field to `ServerConfig` dataclass in `config.py`
- [x] 1.3 Update `_parse_server()` to read the `mdns` field from YAML
- [x] 1.4 Write unit tests for updated `ServerConfig` parsing (mdns default false, mdns true)

## 2. Config Write-Back

- [x] 2.1 Add `write_config(config: Config, path: Path) -> None` using `ruamel.yaml` that preserves comments
- [x] 2.2 Write unit tests for `write_config` — verify comment preservation and round-trip correctness
- [x] 2.3 Add `find_writable_config_path() -> Path` that returns the first writable config path (creates `~/.config/voltkeeper/` dir if needed)

## 3. POST /api/reload and POST /api/shutdown Endpoints

- [x] 3.1 Add `POST /api/shutdown` route to `api.py` (authenticated, returns 202, triggers graceful shutdown via asyncio Event)
- [x] 3.2 Add `POST /api/reload` route to `api.py` (authenticated, re-reads config file, applies hot-reloadable fields, returns JSON with `reloaded`, `restart_required`, optional `reason`)
- [x] 3.3 Implement hot-reload logic: update `DeviceManager` device list and `ScanConfig` without restart; detect host/port changes and flag as restart-required
- [x] 3.4 Write tests for `/api/shutdown` — authorized returns 202, unauthorized returns 401
- [x] 3.5 Write tests for `/api/reload` — hot-reloadable change applied, restart-required change flagged, parse error returns 400

## 4. daemon stop (real implementation)

- [x] 4.1 Implement `daemon_stop` in `cli.py`: if `~/.config/systemd/user/voltkeeper.service` exists, run `systemctl --user stop voltkeeper` and print what it's doing; otherwise call `POST /api/shutdown`
- [x] 4.2 Print confirmation after successful stop; print informative error and exit non-zero if daemon unreachable and no unit file found
- [x] 4.3 Write tests for `daemon_stop` logic (systemctl path, API path, error path)

## 5. voltkeeper config Command Group

- [x] 5.1 Add `config` group to `cli.py` with subcommands: `show`, `set`, `add-device`, `remove-device`
- [x] 5.2 Implement `config show`: find and print config with masked API key, print config file path
- [x] 5.3 Implement `config set <key> <value>`: validate key against allowlist, write via `write_config`, call `/api/reload` if daemon reachable, report hot-reload vs restart-required
- [x] 5.4 Implement `config add-device <address> [--name <name>]`: normalize address, check for duplicate, append, write, reload
- [x] 5.5 Implement `config remove-device <address>`: find and remove entry, write, reload; no-op if not found
- [x] 5.6 Write unit tests for each config subcommand (show masked key, set valid/invalid key, add duplicate, remove missing)

## 6. daemon install / uninstall

- [x] 6.1 Implement `daemon install` in `cli.py`: detect existing unit file (idempotent path), generate API key if absent, locate `voltkeeperd` binary, write config, write hardened unit file, run systemctl commands, print transparent summary
- [x] 6.2 Implement `--lan` flag for `daemon install`: set `server.host: "0.0.0.0"` and `server.mdns: true` in config; print API key with security note
- [x] 6.3 Implement idempotent path: if unit file exists, print service status (via `systemctl --user is-active`), config path, URL, log command, and exit 0
- [x] 6.4 Implement `daemon uninstall`: prompt for confirmation, run `systemctl --user stop/disable`, remove unit file, run `daemon-reload`, print summary; no-op if not installed
- [x] 6.5 Write unit tests for `daemon install` (first install, already installed, --lan flag sets correct config fields)
- [x] 6.6 Write unit tests for `daemon uninstall` (removes unit file, preserves config, no-op if not installed)

## 7. mDNS Advertising

- [x] 7.1 Add `MdnsAdvertiser` class (or module-level functions) in a new `src/voltkeeper/mdns.py` using `python-zeroconf`; advertises `voltkeeper-{hostname}._http._tcp.local.` on the configured port
- [x] 7.2 Integrate mDNS startup into `Daemon._run()`: start `MdnsAdvertiser` when `config.server.mdns` is true and host is non-loopback; shut it down cleanly in `_shutdown()`
- [x] 7.3 Write unit tests for `MdnsAdvertiser` — verify service name format, verify not started when host is loopback

## 8. Docs Update

- [x] 8.1 Rewrite `docs/source/user-guide/daemon.md` around the install-first workflow: `daemon install`, `daemon install --lan`, how to reach the Web UI, `daemon stop`, how to uninstall
- [x] 8.2 Add a section to `daemon.md` explaining `voltkeeperd` vs `voltkeeper daemon` (binary for ExecStart vs CLI management group)
- [x] 8.3 Add a note to `daemon.md` on the BLE exclusivity conflict: stop the daemon before running direct BLE commands (`load-test`, direct `status`, etc.)
- [x] 8.4 Update `docs/source/user-guide/systemd.md`: remove the hand-written unit file example for the main daemon (replaced by `daemon install`); keep the `mqtt-publish-service` and `mqtt-listen-service` sections; add a note on system-level install as the advanced path
- [x] 8.5 Run `mise run docs-lint` and `mise run docs-format-check` and fix any issues

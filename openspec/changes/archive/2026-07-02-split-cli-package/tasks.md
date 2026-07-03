## 1. Baseline capture

- [x] 1.1 Capture `voltkeeper --help`, `voltkeeper daemon --help`, and `voltkeeper config --help` output to temp files for post-split comparison
- [x] 1.2 Run the full suite and record it green (`mise run test-fast`)

## 2. Source split

- [x] 2.1 Create `src/voltkeeper/cli/` with `__init__.py` (root group + version option) and `_helpers.py` (`_close_loop`, `_device_from_scan`, `_resolve_daemon_url`, `_discover_api_key`, `SERVICE_UUID`)
- [x] 2.2 Move command modules verbatim per the design layout: `scan.py`, `status.py`, `write.py`, `mqtt.py`, `services.py`, `loadtest.py`, `verify.py`, `daemon.py` (incl. `_make_unit_file`), `config.py`; absolute imports for non-CLI modules; delete `cli.py`
- [x] 2.3 Wire command registration in `__init__.py`; verify importing `voltkeeper.cli` registers all commands exactly once
- [x] 2.4 Update `patch("voltkeeper.cli.<name>")` targets across `tests/` to the new module paths (grep `voltkeeper.cli` in tests/)
- [x] 2.5 Verify: captured `--help` outputs identical; `git diff --color-moved=dimmed-zebra` shows moves only (imports/headers excepted); full suite green; commit source split

## 3. Test split

- [x] 3.1 Split `tests/test_voltkeeper.py`: CLI suites into per-command-module files under `tests/cli/`, non-CLI suites (core utils, device handler, MQTT client, BLE client serialization/disconnect, source-change watcher) into `tests/test_<module>.py` files; bodies verbatim, shared fixtures to `conftest.py` as needed
- [x] 3.2 Verify no test lost: test count before == after (`pytest --collect-only -q | tail -1`); full suite green; commit test split

## 4. Docs and verification

- [x] 4.1 Grep `docs/source/` for `cli.py` module-path references (developer docs, contributing guide); update any found — user-guide pages reference commands by name and should need no changes; verify nav needs no update
- [x] 4.2 Run `mise run check` and confirm clean

## Context

`cli.py` (2,219 lines) defines the root `cli` group plus 20 commands across three Click groups (root, `daemon`, `config`) and ~18 helper functions. `pyproject.toml` exposes `voltkeeper.cli:cli` as the console entry point, and `tests/test_voltkeeper.py` (4,122 lines) imports `cli` and patches names like `voltkeeper.cli.load_config` — patch targets are the main coupling that moves with the code. This is a structural refactor under the repo rule against rewriting implementations: every function body moves verbatim.

## Goals / Non-Goals

**Goals:**
- One module per command group; helpers live with their only consumer, shared helpers in one module.
- `voltkeeper.cli:cli` entry point and `from voltkeeper.cli import cli` keep working unchanged.
- Test file split that mirrors the source split, enabling targeted runs (e.g. `pytest tests/cli/`).
- Byte-identical CLI behavior: same commands, options, defaults, help text, output, exit codes.

**Non-Goals:**
- No refactoring of function bodies, no coverage improvements, no new tests (review item 4 is separate).
- No change to `daemon.py`, `api.py`, `mqtt_client.py`, or any non-CLI module.
- No renames of commands, options, or helper functions beyond module placement.

## Decisions

**1. Package layout — grouped by command, helpers follow their consumer.**

```
src/voltkeeper/cli/
  __init__.py     # cli root group + version option; imports submodules to register commands; re-exports for compat
  _helpers.py     # _close_loop, _device_from_scan, _resolve_daemon_url, _discover_api_key, SERVICE_UUID
  scan.py         # scan
  status.py       # status, _print_power_section, _print_status, _field_hint, _print_verbose, _status_via_daemon
  write.py        # write, _show_field_help, _write_via_daemon, _parse_field_value
  mqtt.py         # mqtt-publish, mqtt-listen
  services.py     # mqtt-publish-service, mqtt-listen-service
  loadtest.py     # load-test (named to avoid clashing with voltkeeper.load_test module)
  verify.py       # verify, _print_tier_summary, _skip_remaining, _finish
  daemon.py       # daemon group: start, status, stop, install, uninstall, _make_unit_file
  config.py       # config group: show, set, add-device, remove-device, _try_reload_daemon
```

Registration happens by importing each submodule in `__init__.py` after defining the root group (submodules use `@cli.command(...)` via a late import or by taking the group from a shared module). Alternative — a `cli/root.py` defining the group with `__init__.py` only re-exporting — chosen detail left to implementation; the invariant is that `__init__` exposes `cli` and importing the package registers all commands exactly once.

**2. `cli/daemon.py` and `cli/config.py` may shadow `voltkeeper.daemon` / `voltkeeper.config` in intra-package imports — use absolute imports.**
Inside the package, `from ..daemon import ...` vs `from . import daemon` is easy to confuse. All imports of non-CLI modules use the absolute `from voltkeeper.config import ...` form to keep the distinction obvious. (Same reasoning as `loadtest.py` avoiding the `load_test` name.)

**3. Move-only discipline, verified by diff.**
Each function moves with its decorators, docstring, and comments intact. Verification: `git diff --color-moved=dimmed-zebra` should show essentially all source lines as moves; any non-move line needs a reason (import fixes, module docstrings/ABOUTME headers only).

**4. Test split mirrors the source split, plus extraction of non-CLI suites.**
`tests/test_voltkeeper.py` currently holds more than CLI tests. Split into files matching what they test — CLI tests per command module (`tests/cli/test_status.py`, `tests/cli/test_config_cmds.py`, …) and the non-CLI suites (core utils, device handler, MQTT client, BLE client serialization/disconnect) into their own `tests/test_<module>.py` files. Test bodies move verbatim; only imports and `patch("voltkeeper.cli.<name>")` targets change to the new module paths. Shared fixtures move to `tests/conftest.py` if more than one new file needs them.

**5. Update patch targets rather than adding compatibility re-exports for privates.**
`__init__.py` re-exports only what external code legitimately imports (`cli`). Private helpers are not re-exported to keep old patch targets alive — tests update to patch where the name now lives. Re-exporting privates would freeze the old layout forever.

## Risks / Trade-offs

- [Click command registration order changes `--help` listing] → Click sorts commands alphabetically by default; verify `voltkeeper --help` output is identical before/after as part of the tasks.
- [A missed `patch()` target fails loudly but late] → The full suite is the safety net; grep for `voltkeeper.cli` across `tests/` as an explicit task.
- [Import cycles between cli submodules and `_helpers`] → Helpers module imports nothing from command modules; command modules import only downward (helpers, non-CLI packages).
- [Large diff obscures review] → `--color-moved` verification plus splitting the work into two commits (source split, then test split) keeps each reviewable.

## Migration Plan

Two commits on one branch: (1) source package split with all existing tests green against updated imports, (2) test file split. No user-facing migration; `pip`/`pipx` entry points resolve the same object. Rollback is reverting the commits.

## Open Questions

None.

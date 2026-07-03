## Why

`src/voltkeeper/cli.py` is 2,219 lines mixing five concerns: command definitions, output formatting (`_print_verbose` alone spans ~280 lines), systemd unit generation, daemon HTTP client calls, and config editing. Its test coverage (39%) is a symptom — the formatting and service-file logic is hard to reach through Click, and its test file `tests/test_voltkeeper.py` has grown to 4,122 lines covering CLI, core utils, device handler, MQTT, and BLE client concerns in one module. Both files are the main obstacle to targeted testing (2026-07-02 review, item 5).

## What Changes

- `voltkeeper/cli.py` becomes the `voltkeeper/cli/` package: one module per command group, shared helpers in one place, with `cli/__init__.py` exposing the same `cli` Click group so the `voltkeeper.cli:cli` entry point and every existing import keep working.
- Pure code movement — no behavior, command name, option, output, or help-text changes. No function bodies are rewritten.
- `tests/test_voltkeeper.py` is split along the same seams into per-area test files; test bodies move unchanged except for import/patch-target paths that follow the moved code.

## Capabilities

### New Capabilities

- `cli-package-structure`: The CLI is organized as a package with one module per command group; the public entry point, command surface, and all existing import paths remain stable.

### Modified Capabilities

<!-- none — this is a structural refactor; no existing requirement changes -->

## Impact

- `src/voltkeeper/cli.py` → `src/voltkeeper/cli/` (roughly: root group, scan, status/formatting, write, mqtt, services, load-test, verify, daemon, config, shared helpers).
- `tests/test_voltkeeper.py` → per-area test files; `unittest.mock.patch` targets referencing `voltkeeper.cli.<name>` update to the new module paths.
- `pyproject.toml` entry points (`voltkeeper = "voltkeeper.cli:cli"`) unchanged and verified.
- No runtime dependencies, config, docs content, or API changes. Docs reference commands by name, not by module path.

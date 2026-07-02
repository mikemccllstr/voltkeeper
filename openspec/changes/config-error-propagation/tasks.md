## 1. ConfigError in the config module

- [x] 1.1 Write failing tests: `load_config()` with a missing file, invalid YAML, non-mapping root, and each `_fail` validation path raises `ConfigError` with the expected message and path; nothing is printed to stderr; no `SystemExit`
- [x] 1.2 Add `ConfigError` to `config.py`; convert `_fail`, `load_config`, and `_find_config` to raise it; confirm tests pass
- [x] 1.3 Update existing config tests that assert `SystemExit`/stderr from library-level calls to assert `ConfigError` instead

## 2. Process-edge handling

- [x] 2.1 Write failing tests: `voltkeeperd` startup with a bad/missing config prints one `voltkeeperd:`-prefixed line and exits 1; each CLI command that reads config (inventory the `load_config` call sites in `cli.py`) prints the message without the daemon prefix and exits 1, no traceback
- [x] 2.2 Catch `ConfigError` in `daemon.py` startup and at the CLI call sites; confirm tests pass

## 3. Reload API

- [x] 3.1 Write a failing test: `POST /api/reload` against a config with a parse error returns 400 whose error message includes the file path and specific problem; the daemon keeps its current config
- [x] 3.2 Replace `except SystemExit` in `api.py`'s reload handler with `except ConfigError`, returning the error text in the 400 body; confirm tests pass
- [x] 3.3 Grep the codebase for remaining `SystemExit`-catching or stderr assertions tied to config loading and clean them up

## 4. Docs and verification

- [x] 4.1 Check `docs/source/user-guide/daemon.md` (config sections) for any description of config error output; update if it shows the old `voltkeeperd:` prefix from CLI commands (no nav changes expected — verify none needed)
- [x] 4.2 Run `mise run check` (lint, typecheck, tests, docs lint/format) and confirm clean

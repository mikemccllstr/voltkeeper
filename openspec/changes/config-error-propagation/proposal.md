## Why

`config.py` reports every failure by printing a `voltkeeperd:`-prefixed message to stderr and calling `sys.exit(1)` — from library code. This makes config loading unusable outside a process-startup context: the API's `POST /api/reload` handler has to catch `SystemExit` to survive a bad config file, and in doing so loses the parse-error detail that the reload spec requires the 400 response to include. CLI `config` subcommands that traverse the same paths print misleading `voltkeeperd:`-prefixed errors, and every test of a config failure has to trap `SystemExit`.

## What Changes

- `config.py` raises a typed `ConfigError` (carrying the human-readable message and the offending path) instead of printing and exiting; the module no longer writes to stderr or calls `sys.exit`.
- Process edges translate the error: `voltkeeperd` startup and CLI `config`/daemon commands catch `ConfigError`, print the message with the appropriate program prefix, and exit 1 — user-visible output for startup failures stays equivalent.
- `POST /api/reload` catches `ConfigError` and returns 400 with the actual error description, satisfying the existing "describes the error" requirement instead of a generic "could not be loaded".
- The `except SystemExit` workaround in `api.py` is removed.

## Capabilities

### New Capabilities

<!-- none — this corrects error propagation behind existing capabilities -->

### Modified Capabilities

- `daemon-config-management`: The reload-failure scenario is tightened — the 400 response includes the specific config error (file, field, reason), not a generic message.
- `cli-error-handling`: New requirement — config file errors encountered by any CLI command or daemon startup produce a friendly single-line error naming the file and problem, with exit code 1 and no traceback.

## Impact

- `src/voltkeeper/config.py` — `ConfigError` exception; `load_config`, `_find_config`, `_parse_*`, `_fail` raise instead of print-and-exit.
- `src/voltkeeper/daemon.py`, `src/voltkeeper/cli.py` — catch `ConfigError` at entry points and exit with message.
- `src/voltkeeper/api.py` — reload handler catches `ConfigError`; `except SystemExit` removed; 400 body carries the error text.
- Tests — config failure tests assert on raised `ConfigError` / printed message instead of `SystemExit` from library code; reload test asserts error detail in the 400 body.

## Context

`config.py` funnels all failures through `_fail()` (print to stderr + `sys.exit(1)`), and `load_config`/`_find_config` do the same inline for missing/unparseable files. Three kinds of callers traverse these paths today: `voltkeeperd` startup (`daemon.py:27`), the `POST /api/reload` handler (`api.py:301`, which wraps the call in `except SystemExit`), and roughly seven CLI `config`/daemon command sites in `cli.py`. Only the first is a context where exiting the process is acceptable, and even there the exit decision belongs to the entry point, not the parser.

## Goals / Non-Goals

**Goals:**
- `config.py` becomes a pure library: failures raise a typed exception; no stderr writes, no `sys.exit`.
- Identical (or better) user-facing behavior at every existing surface: startup failures still print one clear line and exit 1; reload failures return 400 with the real reason.
- Correct program prefix per surface (`voltkeeperd:` only from the daemon entry point).

**Non-Goals:**
- Config schema changes, new validation rules, or new config fields.
- Restructuring `cli.py` (review item 5) — error handling is added at existing call sites as they are.
- Changing `write_config`/`find_writable_config_path` behavior (they raise OSError naturally; that stays).

## Decisions

**1. One exception type, `ConfigError(Exception)`, with `message` and `path` attributes.**
The existing `_fail(field, message, path)` signature maps directly onto a formatted message; a single type keeps the edge handlers trivial (`except ConfigError as e: print/format`). Subtypes (NotFound vs Parse vs Validation) were considered and rejected — no caller today branches on the kind of failure; the reload handler and CLI both just relay the message. Add subtypes when a caller needs them.

**2. Define `ConfigError` in `config.py`, not `bluetooth/exc.py`.**
`bluetooth/exc.py` holds transport-layer errors; config loading is unrelated. Callers already import from `voltkeeper.config`, so the exception lives beside what raises it.

**3. Message format keeps the current `<field> <message> (in <path>)` shape, minus the program prefix.**
The prefix (`voltkeeperd:` or `voltkeeper:`) is applied by the entry point that catches the error, so CLI commands stop printing a daemon prefix. Existing startup output changes only in that respect.

**4. Edge translation is a small shared helper in each entry module, not a decorator framework.**
`daemon.main()` wraps its `load_config` call; the CLI wraps its call sites (or the few command bodies) in `try/except ConfigError → click.secho + sys.exit(1)`. Seven call sites is few enough that explicit handling stays readable; a Click-level global handler would obscure which commands touch config at all.

## Risks / Trade-offs

- [A missed call site lets `ConfigError` escape as a traceback] → Grep-verified call-site inventory in tasks; tests exercise every CLI config command with a broken config file.
- [Tests currently asserting `SystemExit` from config paths break] → Expected; they are updated to assert `ConfigError` (library level) or exit-code-1-with-message (CLI level), which is a strictly better contract.
- [Reload 400 body now includes config file paths] → The endpoint is API-key-protected and local-network scoped; exposing the path to an authenticated operator is the point, not a leak.

## Migration Plan

Single commit, no config or API schema migration. The reload response shape is unchanged (still `{"error": ...}`, 400) — only the message content improves. Rollback is a revert.

## Open Questions

None.

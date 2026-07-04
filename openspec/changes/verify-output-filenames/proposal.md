## Why

The default verify report path `hardware-data/verify-<MODEL>-<YYYY-MM-DD>.yaml` collides when multiple runs happen on the same day — common while iterating — and the second run silently overwrites the first, destroying bench data. The first EL100V2 ground-truth session (2026-07-04) had to be renamed by hand to avoid this.

## What Changes

- Default report filenames become `hardware-data/{verify|verify-ground-truth}_<MODEL>_<YYYY-MM-DDTHHMMZ>.yaml`: underscore-separated components — mode, model, UTC timestamp to the minute. Runs with `--ground-truth` use the `verify-ground-truth` mode component; plain runs use `verify`.
- The report writer SHALL never overwrite an existing file: if the target path exists (default or `--output`), a `_v<N>` component is appended before the extension with the smallest integer N ≥ 2 that makes the path unique.
- **BREAKING** (filename shape only): tooling or habits that expect `verify-<MODEL>-<DATE>.yaml` must adjust; no report content changes.
- `docs/verify.md` is updated to describe the new naming and the no-overwrite rule (this also resolves the known doc drift that says reports are written to the current directory).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `device-verify`: the "output report is a scrubbed YAML file" requirement changes its default path template and gains a no-overwrite guarantee.

## Impact

- `src/voltkeeper/cli/verify.py` — default filename construction (currently `verify-{model}-{date}.yaml`).
- `src/voltkeeper/core/verify.py` — `write_report` (or the caller) gains the uniqueness check.
- `docs/verify.md` — output-path documentation.
- Tests covering default path and collision behaviour.

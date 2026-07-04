## Context

`cli/verify.py` builds the default report path as `hardware-data/verify-{device.type}-{YYYY-MM-DD}.yaml` and `core/verify.py:write_report` opens it with `"w"`, so a second run on the same day silently clobbers the first. Bench sessions are precious (they need physical hardware and an operator), so losing a report is expensive. Mike specified the desired scheme after the first ground-truth run: `verify-ground-truth_EL100V2_2026-07-04T1759Z.yaml`.

## Goals / Non-Goals

**Goals:**
- Collision-free default filenames that sort chronologically and identify mode + model at a glance.
- A hard no-overwrite guarantee for every report write, including explicit `--output` paths.
- `docs/verify.md` matches the actual behaviour.

**Non-Goals:**
- No changes to report content, scrubbing, or the `hardware-data/` default directory.
- No renaming of existing files in `hardware-data/`.

## Decisions

1. **Filename grammar**: `<mode>_<MODEL>_<timestamp>[_v<N>].yaml`, components separated by underscores so the model (which contains no underscores) and timestamp parse unambiguously. `<mode>` is `verify` or `verify-ground-truth` (hyphens within a component are fine; underscores are the separators). Timestamp is UTC, ISO8601 compacted to minute precision with a literal `Z`: `2026-07-04T1759Z`. Minute precision keeps names short; the `_v<N>` fallback covers the two-runs-in-one-minute case rather than adding seconds.
2. **Uniqueness lives in `write_report`**, not the CLI default: the guarantee must also protect `--output` paths and future callers. On collision, insert `_v<N>` before the suffix, N starting at 2 (`file.yaml`, `file_v2.yaml`, `file_v3.yaml`, …). Alternative considered — timestamp-to-seconds only for defaults — rejected because it leaves `--output` unprotected.
3. **Timestamp captured at session start** (when the default name is computed), not at write time, so the filename matches the `verified_at` session rather than the moment of the final write.

## Risks / Trade-offs

- [Callers that depended on a predictable overwrite path for re-runs] → none known in-repo; `--output` plus manual deletion covers the deliberate-replace case.
- [`_v<N>` scan race if two verifies write simultaneously] → not a real scenario (one BLE device, one operator); accept.

## Why

Tier 3 numeric range probing currently spot-checks only a handful of values (boundary points plus a few out-of-range sentinels), which means we cannot confirm every declared-valid value is actually accepted, cannot reliably discover where the true hardware range begins and ends, and cannot detect holes within a declared range. We have empirical evidence that at least one device (AC2A `sys_low_power`) silently accepts values well outside its declared range, and that unranged fields like `dc_eco_power` have non-obvious lower bounds. A complete, structured probe is needed to turn verify runs into reliable device-model evidence.

## What Changes

- Tier 3 numeric probing replaces the sparse ad-hoc sequence with a full **0–255 exhaustive sweep** for every numeric field (UintField, DecimalField, Uint8Field).
- A **pre/in/post-range state machine** controls the sweep: early termination fires only after 2 consecutive rejections in the post-range zone, so ranges that don't start at 0 are discovered correctly.
- The **restore optimization** skips the restore round-trip when the readback already equals the original value (device silently rejected, no state change).
- **`FieldResult`** gains six new fields and drops the `probes` list for numeric fields (bool/enum keep their per-probe list).
- **Status semantics** change: `fail` means only a restore failure left the device in an unknown state. Range discrepancies and in-range rejections are *findings*, not failures.
- A `hardware-data/` folder is added to the repo as the canonical home for all verify output files, with the two existing AC2A YAML files moved there.
- A new **verify interpretation guide** is added to the docs, written for both humans and Claude/agent instances, explaining how to read the new output and how to use findings to update device models.
- The existing user-facing verify doc and the OpenSpec spec for `device-verify` are updated to match the new behaviour.

## Capabilities

### New Capabilities

- `verify-interpretation`: Guide for reading verify output and translating findings into device model updates — covers new output fields, confidence indicators, and a step-by-step workflow for Claude/agent use.

### Modified Capabilities

- `device-verify`: Tier 3 numeric probe algorithm, output field schema, status semantics, and output file storage location all change.

## Impact

- `src/voltkeeper/core/verify.py` — `FieldResult`, `run_tier3_numeric`, `_tier_result_to_dict`
- `tests/test_verify.py` — new and updated tests for `run_tier3_numeric`
- `openspec/specs/device-verify/spec.md` — tier 3 requirement + scenarios updated
- `docs/source/user-guide/verify.md` — tier 3 description, report structure, result codes updated
- `docs/source/user-guide/verify-interpretation.md` — new file
- `docs/source/user-guide/index.md` — add link to new interpretation guide
- `hardware-data/` — new folder; existing `verify-AC2A-*.yaml` files moved here
- CLI default output path updated to write into `hardware-data/`

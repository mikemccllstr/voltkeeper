## Why

Voltkeeper supports a growing list of device models, most marked `TODO(hardware): verify` because they were derived from APK data without hardware testing. There is currently no systematic way for a user with an untested device to confirm that voltkeeper accurately reads and writes their device's settings — or to contribute that evidence back to the project.

## What Changes

- Add `voltkeeper verify <address>` command that runs a six-tier integration test against a live device
- Tier 1–3 run automatically (read/parse, identity writes, probe writes including range boundary testing)
- Tier 4–6 are supervised (prompt before load-affecting toggles, mode changes, and irreversible operations)
- After any tier with failures, the command recommends sharing results before proceeding deeper
- Output is a structured YAML report (serial number and BLE address scrubbed) designed for submission as a GitHub issue attachment
- Add global `FIELD_TIERS` classification mapping field names to risk tiers — single source of truth applied across all device classes

## Capabilities

### New Capabilities

- `device-verify`: The `voltkeeper verify` command — tier structure, run sequence, interactive prompts, output report format, and global field risk classification

### Modified Capabilities

<!-- None — existing capabilities are unchanged in requirements -->

## Impact

- New module: `src/voltkeeper/core/verify.py` — tier runner, field classification, report builder
- New CLI command: `voltkeeper verify` in `src/voltkeeper/cli.py`
- New tests: `tests/test_verify.py`
- No changes to existing device classes or the struct layer
- BLE connection usage follows same pattern as existing `status` command

## Why

A hardware verification run on an EL100V2 (firmware SW#3) revealed two Modbus read failures: a timeout on reads starting at register 2060, and a Modbus exception 3 on register 3035 (UPS mode). The APK v3.0.9 source reads ALL base settings (2000–2084+) as a single contiguous Modbus read — it does NOT split the range. Our code splits it at the 24-register boundary into two reads (2000+24, then 2060+27), and the EL100V2 hardware rejects the second read entirely. The fix aligns our read strategy with what the Bluetti app actually does.

## What Changes

- Merge the two-command base settings read (`Read(2000, 24)` + `Read(2060, 27)`) into a single `Read(2000, 87)` for EL100V2, matching the APK's approach
- Remove the separate `Read(3035, 1)` for UPS mode from control_commands — the APK does not read this register for V2 devices (it hardcodes the UPS display to "Backup")
- **BREAKING**: `ups_mode` remains a writable field (the APK writes to register 3035), but it will no longer be readable via V2 polling — the `InvBaseSettings` struct lacks a `upsMode` field in the APK

## Capabilities

### New Capabilities

- `merged-base-settings-read`: V2 device base settings are read as a single contiguous Modbus read (matching the APK), rather than split across multiple read commands

### Modified Capabilities

- `el100v2-device`: control_commands definition changes — base settings merged into one read, UPS register read removed
- `v2-control-registers`: `writable_ranges` may need adjustment for EL100V2 (UPS range removal or conditionalization)

## Impact

- `src/voltkeeper/core/devices/el100v2.py` — `control_commands` property and register imports
- `src/voltkeeper/core/devices/v2_base.py` — `writable_ranges` property (removes V1_UPS_MODE range for V2 devices that don't read it, or makes it device-specific)
- `tests/test_voltkeeper.py` — tests referencing UPS mode on EL100V2, and any tests that assert on `control_commands` structure
- `hardware-data/` — AC2A re-verification needed after V2Base writable_ranges change
- Docs: update `docs/source/protocol/modbus-registers.md` if it documents the split-read pattern

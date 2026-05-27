## Why

Hardware testing on the AC2A revealed several gaps in the verify command and its supporting code: a field that doesn't support read-after-write is being probed unnecessarily, the tier-3 probe doesn't respect 8-bit field width, a missing range declaration on `lcd_timeout` leaves the write command unguarded, an enum is missing its `@unique` safety decorator, and the verify docs don't explain key result codes or output file behavior.

## What Changes

- Add `ctrl_led` to `SKIP_AUTO` — boolean field at register 2007 uses write-only/toggle semantics; tier 2/3 probing always produces `no-readback` noise
- Cap tier-3 numeric probe values at 255 for `Uint8Field` types — probing 65535 into a byte-wide field writes 0xFF to both bytes of the shared register, potentially corrupting an adjacent field
- Add `range=(0, 255)` to `lcd_timeout` (register 2008) — hardware rejects 65535; declared range enables write-command validation and constrains tier-3 probe to meaningful values
- Add `@unique` decorator to `EmsCtrlMode` enum — all other enums in `commands.py` have it; the omission is inconsistent and allows silent duplicate-value bugs
- Improve `verify.md`: document `no-readback` result code, `range_discrepancy` flag, and output file location

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `device-verify`: `ctrl_led` added to `SKIP_AUTO`; tier-3 numeric probe caps values at 255 for `Uint8Field`
- `v2-control-registers`: `lcd_timeout` gains a declared range of 0–255

## Impact

- `src/voltkeeper/core/verify.py` — `SKIP_AUTO`, `run_tier3_numeric`
- `src/voltkeeper/core/devices/ac2a.py` — `lcd_timeout` field registration
- `src/voltkeeper/core/commands.py` — `EmsCtrlMode` enum
- `docs/source/user-guide/verify.md` — three new explanatory sections
- `tests/test_verify.py` — new tests for Uint8Field probe cap and updated SKIP_AUTO

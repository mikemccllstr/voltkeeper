## 1. Update EL100V2 Device Model

- [x] 1.1 Merge base settings reads in `control_commands`: replace `ReadHoldingRegisters(2000, 24)` + `ReadHoldingRegisters(2060, 27)` with `ReadHoldingRegisters(2000, 87)`
- [x] 1.2 Remove `ReadHoldingRegisters(V1_UPS_MODE, 1)` from `control_commands`
- [x] 1.3 Remove `V1_UPS_MODE` from the v2_base import line
- [x] 1.4 Remove `s.add_bool_field("ups_mode", V1_UPS_MODE)` from `_build_control_struct()`
- [x] 1.5 Remove `"ups_mode"` from `WRITABLE_FIELD_NAMES` list
- [x] 1.6 Add `writable_ranges` property override returning `[range(2000, 2087), range(2200, 2218)]`
- [x] 1.7 Update ABOUTME comment — remove `TODO(hardware): verify against physical device` (we now have verify data)

## 2. Update Tests

- [x] 2.1 Remove `El100V2` from `test_v2_all_supporting_devices_expose_ups_mode` list; update its docstring
- [x] 2.2 Add `test_control_commands_merged_read`: assert exactly 2 reads, no Read at 2060 or 3035, Read at 2000 has quantity 87
- [x] 2.3 Add `test_writable_ranges_excludes_ups`: assert `writable_ranges` contains exactly two ranges, neither includes 3035
- [x] 2.4 Add `test_no_ups_mode`: assert `ups_mode` not in `WRITABLE_FIELD_NAMES` and `has_field_setter("ups_mode")` returns False

## 3. Update Documentation

- [x] 3.1 Review `docs/source/protocol/modbus-registers.md` — no changes needed; the register reference table is device-agnostic and `UPS_MODE` at 3035 is still valid for EP500/EP600

## 4. Quality Checks

- [x] 4.1 Run `mise run lint` and fix any issues
- [x] 4.2 Run `mise run typecheck` and fix any issues
- [x] 4.3 Run `mise run test` and confirm all tests pass

## 5. Hardware Verification

- [x] 5.1 Re-verify AC2A to confirm no regression from `writable_ranges` change
- [x] 5.2 Re-verify EL100V2 — Read(2000, 67) works (matches APK count for protocol version 2000). All tier1 blocks pass. lcd_timeout at 2067 is beyond the APK's 67-reg read range, write-only.

# Tasks: EL100V2 Improvements from AC2A Implementation

## 1. Promote array parsers to V2Base

- [ ] 1.1 Write failing tests for generic V2 array parsing: an `El100V2` instance parsing synthetic INV_BASE_INFO (software versions), INV_PV_INFO (PV strings), INV_GRID_INFO / INV_LOAD_INFO / INV_INV_INFO (phases) payloads emits the array keys; include short-payload truncation and empty-entry cases
- [ ] 1.2 Move `_MCU_TYPE_NAMES` to a module-level table in `v2_base.py` and move the five `_fill_*` helpers from `AC2A` to `V2Base`, wiring them into `V2Base.parse()` dispatch
- [ ] 1.3 Delete the `AC2A.parse()` override and the moved helpers from `ac2a.py`; run the full AC2A test suite to confirm behavior is unchanged
- [ ] 1.4 Run 1.1 tests to green; confirm EL30V2 tests still pass (it silently gains the same parsing)

## 2. EL100V2 control-surface changes

- [ ] 2.1 Write failing tests: `has_field_setter` returns False for `sys_low_power`, `sys_high_power`, `led_color`; control struct has no fields at 2022/2023/2078; `ctrl_led` still writable
- [ ] 2.2 Write failing tests: `build_setter_command("charging_mode", "custom")` yields register 2020 value 4; `grid_max_current` accepts 1–15 and rejects 0 and 16
- [ ] 2.3 Remove `sys_low_power`, `sys_high_power`, `led_color` from the EL100V2 control struct and `WRITABLE_FIELD_NAMES`; add `CUSTOM = 4` to the EL100V2 `ChargingMode` enum; add `range=(1, 15)` to `grid_max_current`
- [ ] 2.4 Grep for other references to the removed EL100V2 fields (MQTT discovery, field hints, verify interpretation, docs) and update them
- [ ] 2.5 Run 2.1/2.2 tests to green and the full test suite

## 3. Hardware capture session (requires physical EL100V2; requires `verify-raw-capture` implemented)

- [ ] 3.1 Run raw-capture-enabled `voltkeeper verify` against the live EL100V2 so the report records raw hex for all blocks (HOME, INV_BASE_INFO, INV_PV_INFO, INV_GRID_INFO, INV_LOAD_INFO, INV_INV_INFO, base settings); note device state at capture time (SoC, load, AC/DC state, charging) alongside the report
- [ ] 3.2 Probe `charging_mode = 4` (custom) on hardware during the same session: write, read back, confirm acceptance; record result in hardware-data
- [ ] 3.3 Verify firmware-version keys parsed from the captured INV_BASE_INFO match the versions shown in the Bluetti app (IOT/ARM/DSP/BMS expected)
- [ ] 3.4 Probe a few `grid_max_current` values in the claimed valid range (1–15) to confirm acceptance, complementing the recorded failures at 0–2

## 4. EL100V2 fixture tests

- [ ] 4.1 Promote captured block hex from the verify report into EL100V2 fixtures in `tests/conftest.py`, documented with capture-time device state (per the fixture-promotion workflow in verify.md)
- [ ] 4.2 Write parse tests over the fixtures in `test_device_el100v2.py`, mirroring the AC2A parse-test suite: battery/power/energy fields, firmware versions, PV strings, grid/load/inv phases, control-struct parse
- [ ] 4.3 Run full test suite; confirm pristine output

## 5. Documentation

- [ ] 5.1 Update the EL100V2 user-guide device page: new telemetry keys (firmware versions, PV strings, phase data), CUSTOM charging mode, `grid_max_current` range, and removal of `sys_low_power`/`sys_high_power`/`led_color` (breaking)
- [ ] 5.2 Note in the V2-protocol/device docs that array parsing (versions, PV strings, phases) is now base behavior for all V2 devices, including EL30V2
- [ ] 5.3 Update docs navigation/toctree if any pages were added or renamed; build docs and check for warnings

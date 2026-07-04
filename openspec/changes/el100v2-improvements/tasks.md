# Tasks: EL100V2 Improvements from AC2A Implementation

## 1. Promote array parsers to V2Base

- [x] 1.1 Write failing tests for generic V2 array parsing: an `El100V2` instance parsing synthetic INV_BASE_INFO (software versions), INV_PV_INFO (PV strings), INV_GRID_INFO / INV_LOAD_INFO / INV_INV_INFO (phases) payloads emits the array keys; include short-payload truncation and empty-entry cases
- [x] 1.2 Move `_MCU_TYPE_NAMES` to a module-level table in `v2_base.py` and move the five `_fill_*` helpers from `AC2A` to `V2Base`, wiring them into `V2Base.parse()` dispatch
- [x] 1.3 Delete the `AC2A.parse()` override and the moved helpers from `ac2a.py`; run the full AC2A test suite to confirm behavior is unchanged
- [x] 1.4 Run 1.1 tests to green; confirm EL30V2 tests still pass (it silently gains the same parsing)

## 2. EL100V2 control-surface changes

- [x] 2.1 Write failing tests: `has_field_setter` returns False for `sys_low_power`, `sys_high_power`, `led_color`; control struct has no fields at 2022/2023/2078; `ctrl_led` still writable
- [x] 2.2 Write failing tests: `build_setter_command("charging_mode", "custom")` yields register 2020 value 4; `grid_max_current` accepts 1–15 and rejects 0 and 16
- [x] 2.3 Remove `sys_low_power`, `sys_high_power`, `led_color` from the EL100V2 control struct and `WRITABLE_FIELD_NAMES`; add `CUSTOM = 4` to the EL100V2 `ChargingMode` enum; add `range=(1, 15)` to `grid_max_current`
- [x] 2.4 Grep for other references to the removed EL100V2 fields (no EL100V2-specific references found beyond the device class itself)
- [x] 2.5 Run 2.1/2.2 tests to green and the full test suite

## 3. Hardware capture session (requires physical EL100V2; requires `verify-raw-capture` implemented)

- [x] 3.1 Run raw-capture-enabled `voltkeeper verify` against the live EL100V2 so the report records raw hex for all blocks (HOME, INV_BASE_INFO, INV_PV_INFO, INV_GRID_INFO, INV_LOAD_INFO, INV_INV_INFO, base settings); note device state at capture time (SoC, load, AC/DC state, charging) alongside the report (see `hardware-data/verify-EL100V2-ac-2026-07-03-notes.md`)
- [x] 3.2 Probe `charging_mode = 4` (custom) on hardware during the same session: write, read back, confirm acceptance; record result in hardware-data (accepted, readback 4)
- [x] 3.3 Verify firmware-version keys parsed from the captured INV_BASE_INFO match the versions shown in the Bluetti app (IOT/ARM/DSP/BMS expected) (all four match; app displays raw/100)
- [x] 3.4 Probe a few `grid_max_current` values in the claimed valid range (1–15) to confirm acceptance, complementing the recorded failures at 0–2 (device accepts raw 0–15, rejects 16+: register holds whole amps, not deciamps — DecimalField declaration is wrong, fix pending)

## 4. EL100V2 fixture tests

- [ ] 4.1 Promote captured block hex into EL100V2 fixtures in `tests/conftest.py`: from `verify-EL100V2-ac-2026-07-03.yaml` blocks 100, 1100, 1300, 1400, 1500, 2000, 2200; from `verify-EL100V2-dc2-2026-07-03.yaml` blocks 100 and 1200. Document each with capture-time device state per `hardware-data/verify-EL100V2-2026-07-03-notes.md` (AC run: SoC 100%, ~45 W AC + 16 W DC load, grid ~119 V; dc2 run: SoC 99%, ~102 W DC input, on battery)
- [ ] 4.2 Write parse tests over the fixtures in `test_device_el100v2.py`, mirroring the AC2A parse-test suite and asserting the spec's anchor values: SoC 100/99; arm/dsp/bms versions 218614/220013/108307; pv[0] 102 W / 12.5 V / 8.1 A; gridPhase[0] 46 W / 119.3 V; acPhase[0] 46 W / 119.4 V; invPhase[0] voltage 119.4; grid_max_current parses as 4 from block 2200
- [ ] 4.3 Run full test suite; confirm pristine output

## 5. Documentation

- [x] 5.1 Update the EL100V2 user-guide device page: new telemetry keys (firmware versions, PV strings, phase data), CUSTOM charging mode, `grid_max_current` range, and removal of `sys_low_power`/`sys_high_power`/`led_color` (breaking)
- [x] 5.2 Note in the V2-protocol/device docs that array parsing (versions, PV strings, phases) is now base behavior for all V2 devices, including EL30V2
- [x] 5.3 Update docs navigation/toctree if any pages were added or renamed; build docs and check for warnings

## 6. Bench-findings amendments (from verify-EL100V2-ac-2026-07-03)

- [x] 6.1 Write failing tests: `grid_max_current` setter emits value 15 for input 15 (whole amps, no ÷10 scaling), accepts 0, rejects 16; ECO ranges enforced (`ac_eco_power` 10–40, `dc_eco_power` 5–20, both auto-off times 1–4)
- [x] 6.2 Change `grid_max_current` to a uint field with `unit="A"`, `range=(0, 15)`; add ranges to the four ECO fields
- [x] 6.3 Update the existing group-2 tests that assert the old (1, 15) decimal behavior; run full suite to green
- [x] 6.4 Update device-models.md EL100V2 notes: grid_max_current whole amps 0–15 (0 = Pro Mode disabled), ECO ranges, firmware version display format (raw/100)

# Tasks: Charging-Mode Swap and EL100V2 Pack-Voltage Scale

## 1. Shared enum with corrected values

- [x] 1.1 Write failing tests: `build_setter_command("charging_mode", "turbo")` writes 2 and `"silent"` writes 1 on AC2A and EL100V2; parsing a control block with register 2020 = 1 yields SILENT; EL100V2 CUSTOM still writes 4
- [x] 1.2 Define the shared `ChargingMode` (STANDARD=0, SILENT=1, TURBO=2) in v2_base.py; point ac2a.py, ac180.py, el10v2.py, el30v2.py, ac60.py, el400.py at it and delete their local enums; correct el100v2.py's local extension (SILENT=1, TURBO=2, CUSTOM=4) with a cross-reference comment
- [x] 1.3 Run 1.1 tests to green

## 2. Sweep old-label assumptions out of tests

- [x] 2.1 Update `test_build_setter_charging_mode` (TURBO now 2) and the EL100V2 DC-control fixture test: assert SILENT (the device's actual state at capture) and remove the swap-tripwire comment
- [x] 2.2 Correct the conftest AC2A `_CONTROL_HEX` comment (`charging_mode=TURBO=1` → SILENT=1); confirm `tests/fixtures/ac2a_baseline.json` is unaffected (raw int `chargingMode` from HOME telemetry)
- [x] 2.3 Grep tests for remaining TURBO/SILENT value assumptions across all seven devices; fix any found
- [x] 2.4 Run full test suite to green

## 3. EL100V2 pack-voltage scale

- [x] 3.1 Write failing tests: parsing the AC-run HOME fixture yields `packTotalVoltage` 53.50, the DC-run fixture 53.33
- [x] 3.2 Add `DEFAULT_PACK_VOLTAGE_SCALE = 2` to `El100V2`; update the stale v2_base.py comment ("AC2A is the known exception") to describe the actual ÷10/÷100 split, keeping the verify-on-hardware guidance
- [x] 3.3 Run 3.1 tests to green and the full suite

## 4. Documentation

- [x] 4.1 write.md: charging_mode enum entry notes the corrected mapping and the breaking label flip; man page if it lists modes
- [x] 4.2 device-models.md: resolve the "mapping unresolved" caveat in the EL100V2 notes with the confirmed values; state the EL100V2 pack-voltage scale
- [x] 4.3 modbus-registers.md and contributing-devices.md: correct any turbo/silent value tables; document the PLP024-series exception (standard=2, turbo=3) for future device authors
- [x] 4.4 Build docs; confirm no new warnings

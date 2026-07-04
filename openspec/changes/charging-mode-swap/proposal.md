# Proposal: Charging-Mode Swap and EL100V2 Pack-Voltage Scale

## Why

Two hardware-confirmed interpretation errors ship in current V2 device support. First, every V2 `ChargingMode` enum has TURBO and SILENT reversed: writing `charging_mode turbo` (register 2020 = 1) put a live EL100V2 into **Silent** mode on its own display (bench session 2026-07-03), matching APK v3.0.10's `DeviceSettingsChgModeActivity` (standard=0, silent=1, turbo=2, custom=4 for non-PLP024 devices). Second, EL100V2 pack voltage is reported 10× too high (530.5 V for a 56 V-class pack): `El100V2` never overrides `DEFAULT_PACK_VOLTAGE_SCALE`, unlike its siblings AC2A/EL10V2/EL30V2 which use ÷100 — the captured HOME raw (0x14E6 = 5350 at 100% SoC, 5333 at 99%) decodes to 53.50 V / 53.33 V only at ÷100.

## What Changes

- **BREAKING** Correct the V2 `ChargingMode` values to STANDARD=0, SILENT=1, TURBO=2 across all seven V2 device modules that write register 2020 (AC2A, EL100V2, AC180, EL10V2, EL30V2, AC60, EL400). Writes of `turbo`/`silent` change their physical effect (to the one the label always claimed), and parsed/MQTT-published labels for existing register values flip.
- Consolidate the seven identical per-module `ChargingMode` enums into one shared V2 enum; EL100V2 keeps a local extension adding `CUSTOM = 4` (APK gates custom mode to EL100V2 in this family).
- **BREAKING** Fix EL100V2 pack voltage: `DEFAULT_PACK_VOLTAGE_SCALE = 2` (÷100), so `packTotalVoltage` drops 10× to the physical value. Anchored by fixture tests against the 2026-07-03 captures.
- Update all references baked on the old labels: EL100V2/AC2A fixture tests and comments, user-guide and protocol docs (including resolving the "mapping unresolved" note in device-models.md).

## Capabilities

### New Capabilities

- `v2-charging-mode`: the shared V2 charging-mode enum — register 2020 value semantics, the corrected label mapping, and the EL100V2-only CUSTOM extension.

### Modified Capabilities

- `el100v2-device`: pack voltage scale becomes ÷100 (hardware-anchored); charging-mode enum values corrected per the shared mapping.

## Impact

- `src/voltkeeper/core/devices/`: v2_base.py (shared enum), ac2a.py, el100v2.py, ac180.py, el10v2.py, el30v2.py, ac60.py, el400.py (duplicate enums removed / values corrected; EL100V2 scale override).
- Tests: `test_device_el100v2.py` (the `test_dc_run_control` swap tripwire and charging-mode setter tests), `tests/conftest.py` AC2A control-block comment, per-device charging-mode tests; new pack-voltage fixture anchors (53.50 / 53.33 V).
- Docs: write.md, device-models.md, modbus-registers.md, contributing-devices.md, man page — wherever turbo/silent values or the unresolved-mapping caveat appear.
- Downstream: MQTT/Home Assistant consumers see corrected `charging_mode` labels and a 10×-smaller EL100V2 `packTotalVoltage`; both are deliberate corrections, called out as breaking.

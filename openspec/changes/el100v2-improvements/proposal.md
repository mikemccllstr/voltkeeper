# EL100V2 Improvements from AC2A Implementation

## Why

The AC2A implementation is more complete than the EL100V2's: it parses MCU software versions, per-string PV data, and per-phase grid/load/inverter data from register blocks that the EL100V2 also polls but currently discards. APK v3.0.10 analysis confirms these array parsers are generic V2-protocol behavior (`ProtocolParserV2.parseInvBaseInfo` and friends parse them for every V2 device), not AC2A-specific. Meanwhile, the same analysis plus our own hardware verify capture (verify-EL100V2-2026-05-30) show the EL100V2 exposes writable fields the device does not actually support, and misses the CUSTOM charging mode it does support.

## What Changes

- Promote AC2A's array parse helpers to `V2Base` so all V2 devices (including EL100V2) gain them:
  - MCU software version array from INV_BASE_INFO (resolves the unmapped EL100V2 ARM/DSP version gap; APK firmware list for the EL100V2 chain is IOT/ARM/DSP/BMS)
  - Per-string PV data from INV_PV_INFO
  - Per-phase grid/load/inverter data from INV_GRID_INFO / INV_LOAD_INFO / INV_INV_INFO (gives EL100V2 its first AC and grid voltage/current readings)
- Add `CUSTOM = 4` to the EL100V2 `ChargingMode` enum (APK sets `chgModeCustom=true` for EL100V2; custom mode is written to the same CHARGING_MODE register 2020)
- Add range `(1, 15)` to EL100V2 `grid_max_current` (APK `maxGridChgCurrent` range for non-high-volt EL100V2; explains verify-capture write failures at 0–2 A)
- **BREAKING** Remove `sys_low_power` and `sys_high_power` from EL100V2 writable fields and control struct (APK sets `sysPowerConditions(null)` specifically for EL100V2; verify capture shows both fields fail with range discrepancies and failed restore)
- **BREAKING** Remove `led_color` from EL100V2 writable fields and control struct (verify capture shows values 1–3 rejected with no readback; APK `ledColor` is an explicit opt-in the EL100V2 chain never sets — `ctrl_led` on/off remains)
- Add real captured-bytes test fixtures for EL100V2 register blocks and a parse-test suite mirroring the AC2A's, from data captured in a live BLE session

Explicitly out of scope: the suspected TURBO/SILENT value swap in `ChargingMode` (APK writes silent=1, turbo=2; our enums say the reverse). That affects AC2A too and needs hardware confirmation first — it will be its own change.

## Capabilities

### New Capabilities

- `v2-array-parsing`: Generic V2Base parsing of the array-shaped payloads in INV register blocks — MCU software versions, PV strings, and grid/load/inv phases — available to every V2 device instead of only AC2A.

### Modified Capabilities

- `software-version-display`: Requirements currently scoped to "the AC2A device model" become V2Base-generic; AC2A retains identical behavior through inheritance.
- `el100v2-device`: Writable control fields change — `sys_low_power`, `sys_high_power`, and `led_color` removed; `ChargingMode` gains `CUSTOM = 4`; `grid_max_current` gains range validation `(1, 15)`.

## Impact

- `src/voltkeeper/core/devices/v2_base.py`: gains array parse helpers and dispatch (moved from AC2A)
- `src/voltkeeper/core/devices/ac2a.py`: array helpers and parse dispatch removed in favor of inherited V2Base behavior; `_MCU_TYPE_NAMES` moves with them
- `src/voltkeeper/core/devices/el100v2.py`: control struct and `WRITABLE_FIELD_NAMES` edits; `ChargingMode` enum gains CUSTOM
- `tests/conftest.py` or new fixture module: EL100V2 captured register-block fixtures
- `tests/test_device_el100v2.py`: new parse tests; `tests/test_device_ac2a.py` must stay green (behavior preserved via inheritance)
- Other V2 devices (`el30v2.py`): inherit the new array parsing — telemetry keys may appear for them too
- MQTT/HA consumers: EL100V2 loses `sys_low_power`/`sys_high_power`/`led_color` setters; anything subscribed to those topics is affected
- Docs: user guide device pages for EL100V2 (fields added/removed) and navigation updates

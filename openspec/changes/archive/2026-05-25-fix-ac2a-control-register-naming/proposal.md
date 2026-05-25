## Why

Analysis of the Bluetti Android app APK v3.0.9 reveals that several AC2A control register fields in our implementation have names that don't match the app's internal naming, making the purpose of some controls misleading. Additionally, the app's `InvAdvancedParamsConfig` feature flags show that several fields exposed as writable in our Expert Mode UI are actually hidden by the official app for the AC2A model.

## What Changes

- **BREAKING**: Rename `battery_range_start` (2022) to `sys_low_power` — the APK calls this `sysLowPower`, a system power threshold, not a battery SOC range
- **BREAKING**: Rename `battery_range_end` (2023) to `sys_high_power` — APK name `sysHighPower`
- **BREAKING**: Rename `soc_low` (2075) to `soc_holding_low` — APK name `socHoldingLow`
- **BREAKING**: Rename `soc_high` (2083) to `soc_holding_high` — APK name `socHoldingHigh`
- Mark `system_timezone` (2004) as unverified — the APK does not parse this register from the base settings block
- Document that `grid_max_power`, `grid_max_current`, `chg_max_voltage`, `chg_max_current`, `feed_max_power`, `feed_max_current`, and `inv_voltage` have `InvAdvancedParamsConfig = false` for AC2A, meaning the official app hides them in Expert Mode (registers remain writable for advanced use)
- Update protocol docs (`modbus-registers.md`), user guide (`write.md`), man page, and test fixtures to reflect new field names
- Apply the same renames to EL100V2 which shares these control fields

## Capabilities

### New Capabilities

None — this is a correction of existing capabilities, not a new feature.

### Modified Capabilities

- `v2-control-registers`: Field names for registers 2022, 2023, 2075, 2083 change; `SYSTEM_TIME_ZONE` (2004) is flagged as unverified
- `el100v2-device`: Same field renames apply since EL100V2 shares these control fields with AC2A

## Impact

- **Source**: `ac2a.py`, `el100v2.py`, `ac60.py` — field definitions, `WRITABLE_FIELD_NAMES`, test helpers in `tests/conftest.py`
- **Protocol docs**: `docs/source/protocol/modbus-registers.md` — register name table
- **User docs**: `docs/source/user-guide/write.md`, `docs/source/man/voltkeeper.1.md`
- **MQTT**: `mqtt_client.py` — `NORMAL_DEVICE_FIELDS` entries for renamed fields
- **Tests**: `test_voltkeeper.py`, `test_device_registry.py` — all references to renamed fields
- **OpenSpec specs**: `v2-control-registers/spec.md`, `el100v2-device/spec.md`
- **Breaking for users**: Any MQTT automations, Home Assistant configurations, or scripts referencing the old field names will need updating

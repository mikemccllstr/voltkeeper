## Why

Many writable and readable fields in voltkeeper's verbose output appear as opaque integers (e.g., `inv_freq 1`, `led_color 0`, `Inv Status=3`). The APK v3.0.9 source confirms that most of these are enumerated values with human-readable meanings — 50Hz/60Hz, Off/Cool/Warm/SOS, Cloud/Local/AI mode, etc. Additionally, numeric fields like `ac_eco_power` have validated ranges (10-40W) that are not enforced on writes, and the CLI/Web UI/API interfaces provide no guidance about valid values.

## What Changes

- Convert 5 V2 `UintField` writable fields to `EnumField` with proper enums: `inv_freq` (50Hz/60Hz), `pv_type_set` (PV/Other), `pv2_type_set` (PV/Other/Alternator), `led_color` (Off/Cool/Warm/SOS), `ems_ctrl_mode_set` (Disable/Cloud/Local/DynamicPrice/AI)
- Add range validation to `build_setter_command` for `UintField` and `DecimalField` writes — reject out-of-range values before sending to device
- Add human-readable display for `invWorkingStatus` in CLI verbose output (3/4/5=Normal, 7=Abnormal, others=Unknown)
- Add unit suffixes to CLI verbose display: `dc_eco_auto_off_time` → `"4h"`, `ac_eco_power` → `"10W"`, `inv_freq` → enum name
- Fix CLI `_parse_field_value` to delegate to `build_setter_command` semantics instead of hardcoding charging_mode values
- Add `--help` to `write` command showing valid enum values and numeric ranges for each writable field
- Fix Web UI `charging_mode` dropdown bug (sends `"1"` string but `build_setter_command` expects `"TURBO"`)
- Render Web UI controls dynamically from device writable field definitions instead of hardcoded list
- Add Web UI dropdown controls for new enum fields, numeric inputs with range hints for range-constrained fields
- Return descriptive error messages from HTTP API for out-of-range and invalid enum writes
- Add new enum fields to MQTT `NORMAL_DEVICE_FIELDS` for Home Assistant auto-discovery
- Document `inv_voltage` (2209) as a known enumeration whose mapping depends on `voltType` (undiscovered), with known values documented

## Capabilities

### New Capabilities
- `field-value-semantics`: Enum definitions for 5 register fields, range validation in `build_setter_command`, `invWorkingStatus` display mapping
- `interface-value-display`: CLI help enhancements, unit suffixes, Web UI dynamic controls with dropdowns/ranges, API error messages, MQTT field exposure

### Modified Capabilities
- `v2-control-registers`: Converting `inv_freq`, `pv_type_set`, `pv2_type_set`, `led_color`, `ems_ctrl_mode_set` from `UintField` to `EnumField`; documenting `inv_voltage` voltType dependency
- `ac180-device`: Updating AC180, EL10V2, EL30V2, EL400 classes to use new enum fields
- `v1-control-registers`: V1 `inv_frequency` already uses `InverterFrequency` enum — no change needed, but noted as existing pattern

## Impact

- `src/voltkeeper/core/commands.py` — new enums: `InvFrequency`, `PvType`, `Pv2Type`, `LedColor`, `EmsCtrlMode`
- `src/voltkeeper/core/devices/v2_base.py` — range validation in `build_setter_command`
- `src/voltkeeper/core/devices/ac2a.py` — convert 5 fields from `UintField` to `EnumField`
- `src/voltkeeper/core/devices/ac60.py`, `ac180.py`, `el10v2.py`, `el30v2.py`, `el400.py`, `el100v2.py` — convert applicable fields to `EnumField`
- `src/voltkeeper/cli.py` — `_print_verbose` unit suffixes + invWorkingStatus mapping, `write --help`, `_parse_field_value` fix
- `src/voltkeeper/api.py` — improved error messages for validation failures
- `src/voltkeeper/mqtt_client.py` — new enum fields in `NORMAL_DEVICE_FIELDS`
- `src/voltkeeper/webui/index.html` — dynamic control rendering, charging_mode bug fix
- `docs/source/protocol/modbus-registers.md` — enum value documentation
- `tests/` — new tests for enum parsing, range validation, CLI display, Web UI

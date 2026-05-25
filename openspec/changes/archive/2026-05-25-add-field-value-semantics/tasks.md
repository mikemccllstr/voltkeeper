## 1. Enums in commands.py

- [x] 1.1 Add `InvFrequency` enum (HZ_50=0, HZ_60=1) to `src/voltkeeper/core/commands.py`
- [x] 1.2 Add `PvType` enum (PV=0, OTHER=3) to `commands.py`
- [x] 1.3 Add `Pv2Type` enum (PV=0, OTHER=3, ALTERNATOR=4) to `commands.py`
- [x] 1.4 Add `LedColor` enum (OFF=0, COOL=1, WARM=2, SOS=3) to `commands.py`
- [x] 1.5 Add `EmsCtrlMode` enum (DISABLE=0, CLOUD=3, LOCAL=4, DYNAMIC_PRICE=5, AI=8) to `commands.py`

## 2. V2 Device Class EnumField Conversions

- [x] 2.1 Convert `inv_freq` from UintField to EnumField in AC2A, AC60, AC180, EL10V2, EL30V2, EL100V2, EL400
- [x] 2.2 Convert `pv_type_set` and `pv2_type_set` from UintField to EnumField in AC2A, EL30V2, EL100V2, EL400
- [x] 2.3 Convert `led_color` from UintField to EnumField in AC2A, AC180, EL10V2, EL30V2, EL100V2, EL400
- [x] 2.4 Convert `ems_ctrl_mode_set` from UintField to EnumField in AC2A
- [x] 2.5 Add inv_voltage voltType documentation comment in AC2A, EL30V2, EL100V2, EL400
- [x] 2.6 Import new enums and add to WRITABLE_FIELD_NAMES in each modified device class

## 3. V1 Device Class InverterFrequency Migration

- [x] 3.1-3.4 SKIPPED: V1 InverterFrequency stores actual Hz (50/60) in register 3003, incompatible with V2 InvFrequency (0/1 index). V1 enum kept as-is. See design note.

## 4. Range Validation in build_setter_command

- [x] 4.1 Add `in_range()` check in `v2_base.py` `build_setter_command` for UintField and DecimalField
- [x] 4.2 Add `in_range()` check in `v1_base.py` `build_setter_command` for UintField and DecimalField
- [x] 4.3 Raise `ValueError` with field name and valid range for out-of-range values
- [x] 4.4 Write tests for range enforcement on writes (sys_low_power with range (0,100))

## 5. CLI Display Enhancements

- [x] 5.1 Add unit suffix mapping to `_print_verbose()` — eco_auto_off_time shows "h", eco_power shows "W"
- [x] 5.2 Add `invWorkingStatus` human-readable mapping in MISC section (3/4/5=Normal, 7=Abnormal)
- [x] 5.3 Enum fields already display via `val.name.lower()` — verified all new enums display correctly

## 6. CLI Write Command Help

- [x] 6.1 Add `--help-field` option to `write` command that shows field type, enum values, and range
- [x] 6.2 Update unknown-field error message to suggest `--help-field`
- [x] 6.3 Fix `_parse_field_value` in daemon path to send raw string values instead of hardcoded enum mappings
- [x] 6.4 Write tests for `--help-field` output and error message

## 7. HTTP API Field Discovery Endpoint

- [x] 7.1 Add `GET /api/device/{address}/fields` endpoint to `api.py` returning writable fields with types
- [x] 7.2 For EnumField: return type "enum" with `values` array of member names
- [x] 7.3 For BoolField: return type "bool"
- [x] 7.4 For UintField/DecimalField with range: return type "int" with `range` array [min, max]
- [x] 7.5 Improve error response in `_handle_command` to include field name and reason in 400 JSON body
- [x] 7.6 Write tests for fields endpoint and error response format

## 8. Web UI Dynamic Controls

- [x] 8.1 Fix charging_mode dropdown in `index.html` to send string names not integer strings
- [x] 8.2 Replace hardcoded `writableFields` array with dynamic fetch from `/api/device/{address}/fields`
- [x] 8.3 Render enum-typed fields as `<select>` dropdowns with options matching enum member names
- [x] 8.4 Render bool-typed fields as toggle checkboxes (existing behavior, preserved)
- [x] 8.5 Render int-typed fields with range as `<input type="number">` with min/max attributes

## 9. MQTT Enum Field Exposure

- [x] 9.1 Add `inv_freq` as ENUM field in `NORMAL_DEVICE_FIELDS` with HA select entity (options: hz_50, hz_60)
- [x] 9.2 Add `led_color` as ENUM field in `NORMAL_DEVICE_FIELDS` with HA select entity (options: off, cool, warm, sos)
- [x] 9.3 Add `pv_type_set` as ENUM field (options: pv, other)
- [x] 9.4 Add `ems_ctrl_mode_set` as ENUM field for AC2A (options: disable, cloud, local, dynamic_price, ai)
- [x] 9.5 Handle ENUM type in `_handle_command` payload decoding (already handled for charging_mode, verified for new fields)

## 10. Documentation

- [x] 10.1 Document all new enum value mappings in `modbus-registers.md` for registers 2060, 2061, 2078, 2210, 2241
- [x] 10.2 Document inv_voltage voltType dependency in `modbus-registers.md`
- [x] 10.3 Document invWorkingStatus values (3/4/5=Normal, 7=Abnormal) in `modbus-registers.md`

## 11. Quality Gate

- [x] 11.1 Run `mise run lint` and fix any issues
- [x] 11.2 Run `mise run typecheck` and fix any issues
- [x] 11.3 Run `mise run test` and ensure all tests pass including new tests

## 1. Rename fields in AC2A and EL100V2 device definitions

- [x] 1.1 Rename `battery_range_start` → `sys_low_power` in `ac2a.py` control struct, `WRITABLE_FIELD_NAMES`, and field definition
- [x] 1.2 Rename `battery_range_end` → `sys_high_power` in `ac2a.py` control struct, `WRITABLE_FIELD_NAMES`, and field definition
- [x] 1.3 Rename `soc_low` → `soc_holding_low` in `ac2a.py` control struct, `WRITABLE_FIELD_NAMES`, and field definition
- [x] 1.4 Rename `soc_high` → `soc_holding_high` in `ac2a.py` control struct, `WRITABLE_FIELD_NAMES`, and field definition
- [x] 1.5 Add comment on `system_timezone` (2004) noting APK does not parse this register in `parseInvBaseSettings`
- [x] 1.6 Apply same renames to `el100v2.py` control struct and `WRITABLE_FIELD_NAMES`

## 2. Update MQTT client field configs

- [x] 2.1 Rename `battery_range_start` → `sys_low_power` in `mqtt_client.py` `NORMAL_DEVICE_FIELDS`
- [x] 2.2 Rename `battery_range_end` → `sys_high_power` in `mqtt_client.py` `NORMAL_DEVICE_FIELDS`
- [x] 2.3 Rename `soc_low` → `soc_holding_low` in `mqtt_client.py` `NORMAL_DEVICE_FIELDS`
- [x] 2.4 Rename `soc_high` → `soc_holding_high` in `mqtt_client.py` `NORMAL_DEVICE_FIELDS`

## 3. Update test fixtures and test code

- [x] 3.1 Rename field references in `tests/conftest.py` (comment labels for control bytes)
- [x] 3.2 Rename field references in `tests/test_voltkeeper.py`:
- [x] 3.3 Verify `tests/test_device_registry.py` still passes with renamed fields
- [x] 3.4 Run `mise run test` to confirm all tests pass

## 4. Update protocol documentation

- [x] 4.1 Update `docs/source/protocol/modbus-registers.md`:
  - Rename 2022/2023 entries from `SYS_SOC_LOW_CAPACITY`/`SYS_SOC_HIGH_CAPACITY` to `SYS_LOW_POWER`/`SYS_HIGH_POWER`
  - Rename 2075/2083 entries from `SOC_SET_LOW`/`SOC_SET_HIGH` to `SOC_HOLDING_LOW`/`SOC_HOLDING_HIGH`
  - Add note on `SYSTEM_TIME_ZONE` (2004) that APK does not parse this register
  - Add note block listing which 2200-block controls have `InvAdvancedParamsConfig = false` for AC2A
- [x] 4.2 Update `docs/source/protocol/device-models.md` with AC2A field name corrections

## 5. Update user documentation

- [x] 5.1 Update `docs/source/user-guide/write.md` with new field names and old→new mapping table
- [x] 5.2 Update `docs/source/man/voltkeeper.1.md` with new field names
- [x] 5.3 Add breaking change note with old→new field name mapping

## 6. Update OpenSpec specs

- [x] 6.1 Apply delta spec to `openspec/specs/v2-control-registers/spec.md` (field renames, system_timezone note, remove RV_ENABLE_SET requirement)
- [x] 6.2 Apply delta spec to `openspec/specs/el100v2-device/spec.md` (field renames)

## 7. Final verification

- [x] 7.1 Run `mise run check` to verify lint, typecheck, and tests all pass
- [x] 7.2 Review git diff for completeness and unintended changes

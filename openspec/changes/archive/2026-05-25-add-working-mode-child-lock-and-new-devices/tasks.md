## 1. WORKING_MODE Register and Enum

- [x] 1.1 Add `WorkingMode` enum to `src/voltkeeper/core/commands.py` with values 1=CUSTOMIZED_UPS, 2=PV_PRIORITY_UPS, 3=STANDARD_UPS, 4=TIME_CTRL_UPS, 5=V2_TIME_CTRL_UPS, 11=SELF_CONSUMPTION_EXPORT
- [x] 1.2 Add `WORKING_MODE = 2005` constant to `src/voltkeeper/core/devices/v2_base.py`
- [x] 1.3 Add `WORKING_MODE = 3001` constant to `src/voltkeeper/core/devices/v1_base.py`
- [x] 1.4 Add `working_mode` writable EnumField to V2 device classes (AC2A, AC60, AC200L, AC200M, AC200PL, AC500, EL100V2) in their `_build_control_struct()` methods
- [x] 1.5 Add `working_mode` writable EnumField to V1 device classes (AC300, AC500, EB3A, AC200M) where applicable
- [x] 1.6 Update `build_setter_command()` in `v2_base.py` (or `bluetti_device.py`) to handle EnumField writes for WorkingMode
- [x] 1.7 Write tests for WorkingMode enum serialization, CLI parsing, and register writes
- [x] 1.8 Update `modbus-registers.md` with WORKING_MODE value mapping table

## 2. Child Lock Registers

- [x] 2.1 Add `CTRL_CHILD_LOCK = 2072` and `CHILD_LOCK_LEVEL = 2076` constants to `src/voltkeeper/core/devices/v2_base.py`
- [x] 2.2 Implement child lock write logic: True → 0x20 (bit 5), False → 0x10 (bit 4) for register 2072
- [x] 2.3 Add `child_lock` (BoolField at 2072) and `child_lock_level` (IntField at 2076, range 1-2) to AC180 base class `_build_control_struct()`
- [x] 2.4 Ensure EL10V2 inherits child lock fields from AC180; ensure EL400 and EL30V2 do NOT expose child lock (feature flag `childLockCtrl=false`)
- [x] 2.5 Write tests for child lock ON/OFF bitfield writes and level writes with invalid value rejection
- [x] 2.6 Update `modbus-registers.md` with Child Lock register documentation

## 3. SYSTEM_POWER_OFF Multi-Value Encoding and Sleep Registers

- [x] 3.1 Document SYSTEM_POWER_OFF value encoding (1-4) in `modbus-registers.md`
- [x] 3.2 Add `AUTO_SLEEP_DAYS = 2073`, `REMOTE_STARTUP_SOC = 2074`, `SLEEP_POWER_THRESHOLD = 2079` constants to `v2_base.py`
- [x] 3.3 Add `sleep_power_threshold` (UintField at 2079) and `remote_startup_soc` (UintField at 2074) to EL400 class
- [x] 3.4 Add `sleep_mode` writable BoolField to EL400 that writes value 4 to SYSTEM_POWER_OFF (2013) when enabled
- [x] 3.5 Write tests for sleep register writes and SYSTEM_POWER_OFF value encoding

## 4. AC180 Base Class

- [x] 4.1 Create `src/voltkeeper/core/devices/ac180.py` with AC180 class inheriting from V2Base
- [x] 4.2 Set `type = "AC180"`, `protocol_version = 2000`, `DEFAULT_PACK_VOLTAGE_SCALE = 1` (56V)
- [x] 4.3 Implement `_build_control_struct()` with writable fields: ac_switch, dc_switch, dc_eco_mode, ac_eco_mode, charging_mode, power_lifting, working_mode, ups_mode, inv_freq, child_lock, child_lock_level, sys_low_power, sys_high_power
- [x] 4.4 Implement `control_commands` returning ReadHoldingRegisters for INV_BASE_SETTINGS (2000) and INV_ADVANCE_SETTINGS (2200) blocks
- [x] 4.5 Add `# TODO(hardware): verify against physical device` comment on class
- [x] 4.6 Write tests for AC180 control struct initialization and writable field validation

## 5. EL10V2 Device Class

- [x] 5.1 Create `src/voltkeeper/core/devices/el10v2.py` with EL10V2 class inheriting from AC180
- [x] 5.2 Set `type = "EL10V2"`, override `DEFAULT_PACK_VOLTAGE_SCALE` for 25V nominal
- [x] 5.3 Add EL10V2-specific writable fields beyond AC180 base: `grid_max_input_current`, `soc_holding_low`, `soc_holding_high`
- [x] 5.4 Add `# TODO(hardware): verify against physical device` comment on class
- [x] 5.5 Write tests for EL10V2 with fabricated hex data at 25V voltage scaling

## 6. EL30V2 Device Class

- [x] 6.1 Create `src/voltkeeper/core/devices/el30v2.py` with EL30V2 class inheriting from V2Base
- [x] 6.2 Set `type = "EL30V2"`, `protocol_version = 2000`, override `DEFAULT_PACK_VOLTAGE_SCALE` for 25V
- [x] 6.3 Implement `_build_control_struct()` mirroring EL100V2 writable fields: ac_switch, dc_switch, dc_eco_mode, ac_eco_mode, charging_mode, power_lifting, working_mode, inv_voltage, inv_freq, chg_max_voltage, chg_max_current, grid_max_power, grid_max_current, soc_holding_low, soc_holding_high, grid_max_input_current, ctrl_grid, ctrl_feed, feed_max_power
- [x] 6.4 Add `# TODO(hardware): verify against physical device` comment on class
- [x] 6.5 Write tests for EL30V2 with fabricated hex data at 25V voltage scaling

## 7. EL400 Device Class

- [x] 7.1 Create `src/voltkeeper/core/devices/el400.py` with EL400 class inheriting from V2Base
- [x] 7.2 Set `type = "EL400"`, `protocol_version = 2000`, `DEFAULT_PACK_VOLTAGE_SCALE = 1` (56V)
- [x] 7.3 Implement `_build_control_struct()` with all standard fields plus EL400-unique: `remote_power_ctrl`, `sleep_power_threshold`, `remote_startup_soc`
- [x] 7.4 Implement `sleep_mode` write mapping (True → value 4 to SYSTEM_POWER_OFF 2013)
- [x] 7.5 Add `# TODO(hardware): verify against physical device` comment on class
- [x] 7.6 Write tests for EL400 with fabricated hex data, including sleep/remote power fields

## 8. Device Registry and Regex Updates

- [x] 8.1 Add `"EL10V2"` prefix matching in `_DEVICE_NAME_SN_RE` regex in `src/voltkeeper/bluetooth/__init__.py`
- [x] 8.2 Add `"EL30V2"` prefix matching in regex
- [x] 8.3 Add `"EL400"` prefix matching in regex
- [x] 8.4 Add import and registry entry for EL10V2, EL30V2, and EL400 in `_device_registry()`
- [x] 8.5 Write tests for device name regex matching and `build_device()` returning correct class instances

## 9. Protocol Documentation Updates

- [x] 9.1 Add WORKING_MODE register (3001/2005) with full WorkingMode value mapping to `modbus-registers.md`
- [x] 9.2 Add Child Lock registers (2072, 2076) to `modbus-registers.md` with bitfield/value documentation
- [x] 9.3 Document SYSTEM_POWER_OFF multi-value encoding (1-4) in `modbus-registers.md`
- [x] 9.4 Add sleep config registers (2073, 2074, 2079) to `modbus-registers.md`
- [x] 9.5 Add EL10V2, EL30V2, EL400, AC180, PLP022 entries to `device-models.md` with model numbers, voltages, and feature notes

## 10. Quality Gate

- [x] 10.1 Run `mise run lint` and fix any issues
- [x] 10.2 Run `mise run typecheck` and fix any issues
- [x] 10.3 Run `mise run test` and ensure all tests pass including new tests
